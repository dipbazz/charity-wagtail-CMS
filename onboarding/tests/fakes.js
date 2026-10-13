// Fake Apps Script services that run onboarding/form-script.gs in Node, for form-script.test.js.
// They keep the rules of the real services that the script has tripped on, such as Forms
// refusing to delete a page that a choice still goes to.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PACK = path.join(__dirname, '..');
const SCRIPT = fs.readFileSync(path.join(PACK, 'form-script.gs'), 'utf8');
const fill = s => s.replace(/\{name_ne\}/g, 'ब्राइटवेल').replace(/\{name_en\}/g, 'Brightwell')
  .replace(/\{domain\}/g, 'brightwell.example').replace(/\{version\}/g, '0.5.0')
  .replace(/\{demo_url\}/g, 'https://demo.example.org');
const CSV = fill(fs.readFileSync(path.join(PACK, 'questions.csv'), 'utf8'));
const GUIDE = fill(fs.readFileSync(path.join(PACK, 'guide.md'), 'utf8'));

function parseCsv(text) {
  const rows = []; let row = []; let field = ''; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; } else if (c === '"') q = false; else field += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (c !== '\r') field += c;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}

// Any method not faked returns another chainable fake; build() returns a plain object.
const chain = (base = {}) => new Proxy(base, { get: (t, k) => (k in t ? t[k] : k === 'build' ? () => ({}) : () => chain()) });
const iter = list => { let i = 0; return { hasNext: () => i < list.length, next: () => list[i++] }; };

function makeWorld({ sheetId = 'sheet1', props = {}, formItems = [], rows, header, setup = () => {} }) {
  let nextId = 1000;
  const files = {};
  const folder = {
    getId: () => 'folder1',
    files: [],
    getFilesByName(name) { return iter(this.files.filter(f => f.name === name && !f.trashed)); },
  };
  function addFile(id, name, mime, extra = {}) {
    const f = Object.assign({
      id, name, mime, trashed: false, created: new Date(nextId++),
      getId: () => id, getName: () => name, getMimeType: () => mime, isTrashed() { return this.trashed; },
      setTrashed(v) { this.trashed = v; }, getDateCreated() { return this.created; },
      getUrl: () => 'https://docs.google.com/document/d/' + id + '/edit',
      getParents: () => iter([folder]), moveTo() {},
    }, extra);
    files[id] = f; folder.files.push(f); return f;
  }
  addFile(sheetId, 'Brightwell content tracker', 'sheet');
  addFile('csv-old', 'questions.csv', 'text/csv', { getBlob: () => ({ getDataAsString: () => 'stale' }) });
  addFile('csv1', 'questions.csv', 'text/csv', { getBlob: () => ({ getDataAsString: () => CSV }) });
  addFile('md1', 'guide.md', 'text/markdown', { getBlob: () => ({ setContentType() { return this; }, text: GUIDE }) });
  addFile('doc1', 'Brightwell website guide', 'application/vnd.google-apps.document');

  function makeSheet(name, values) {
    return {
      name, values,
      getName() { return this.name; }, setName(n) { this.name = n; },
      getFormUrl: () => (name === 'Responses' ? 'https://docs.google.com/forms/d/form1' : null),
      getDataRange() { const v = this.values; return { getValues: () => v.map(r => r.slice()) }; },
      getLastRow() { return this.values.length; }, getLastColumn() { return this.values[0].length; },
      getMaxRows: () => 1000,
      getRange(r, c, nr = 1, nc = 1) {
        const sh = this;
        const ensure = () => { while (sh.values.length < r - 1 + nr) sh.values.push(new Array(sh.values[0].length).fill('')); };
        return chain({
          setValue(v) { ensure(); sh.values[r - 1][c - 1] = v; return this; },
          setValues(vs) { ensure(); vs.forEach((row, i) => row.forEach((v, j) => { sh.values[r - 1 + i][c - 1 + j] = v; })); return this; },
          clearContent() { ensure(); for (let i = 0; i < nr; i++) for (let j = 0; j < nc; j++) sh.values[r - 1 + i][c - 1 + j] = ''; return this; },
        });
      },
      getConditionalFormatRules: () => [], setConditionalFormatRules() {}, getFilter: () => null,
      setFrozenRows() {}, setFrozenColumns() {}, setColumnWidth() {},
    };
  }
  const requirements = makeSheet('Requirements', [header, ...rows]);
  const sheets = [requirements, makeSheet('Responses', [['Timestamp']])];
  let alert = '';
  const ss = {
    getId: () => sheetId, getName: () => 'Brightwell content tracker',
    getSheetByName: n => sheets.find(s => s.name === n) || null,
    getSheets: () => sheets, insertSheet(n) { const s = makeSheet(n, [['', '']]); sheets.push(s); return s; },
    toast() {},
  };

  const ItemType = { TEXT: 'TEXT', PARAGRAPH_TEXT: 'PARAGRAPH_TEXT', MULTIPLE_CHOICE: 'MULTIPLE_CHOICE', CHECKBOX: 'CHECKBOX', PAGE_BREAK: 'PAGE_BREAK', FILE_UPLOAD: 'FILE_UPLOAD' };
  const forms = {};
  function makeForm(id, title) {
    const form = {
      id, title, description: '', items: [], destination: null, created: 0,
      getId: () => id, getPublishedUrl: () => 'https://forms/' + id + '/viewform', getEditUrl: () => 'https://forms/' + id + '/edit',
      setTitle(t) { this.title = t; return this; }, setDescription(d) { this.description = d; return this; },
      setConfirmationMessage() { return this; }, setShowLinkToRespondAgain() { return this; },
      setAllowResponseEdits() { return this; }, setProgressBar() { return this; },
      getDestinationId() { if (!this.destination) throw new Error('none'); return this.destination; },
      setDestination(t, d) { this.destination = d; },
      getResponses: () => [],
      getItems(type) { return this.items.filter(i => !type || i.type === type); },
      getItemById(n) { const it = this.items.find(i => i.id === Number(n)); if (!it) throw new Error('no item'); return it; },
      deleteItem(it) {
        // Like Forms: a page can't be deleted while a choice still goes to it.
        if (this.items.some(i => i.choices.some(c => c.page === it))) throw new Error('Invalid data updating form.');
        this.items = this.items.filter(i => i !== it);
      },
      moveItem(it, index) { this.items = this.items.filter(i => i !== it); this.items.splice(index, 0, it); },
      add(type) {
        const item = makeItem(nextId++, type, ''); this.items.push(item); this.created += 1;
        return { getId: () => item.id }; // typed items lack as*Item(), like the real ones
      },
      addTextItem() { return this.add(ItemType.TEXT); }, addParagraphTextItem() { return this.add(ItemType.PARAGRAPH_TEXT); },
      addMultipleChoiceItem() { return this.add(ItemType.MULTIPLE_CHOICE); }, addCheckboxItem() { return this.add(ItemType.CHECKBOX); },
      addPageBreakItem() { return this.add(ItemType.PAGE_BREAK); },
    };
    function makeItem(iid, type, t) {
      return {
        id: iid, type, title: t, help: '', choices: [], other: false,
        getId() { return this.id; }, getType() { return this.type; }, getTitle() { return this.title; },
        getIndex() { return form.items.indexOf(this); },
        setTitle(x) { this.title = x; return this; }, setHelpText(x) { this.help = x; return this; },
        setRequired() { return this; }, setGoToPage(x) { this.goTo = x; return this; },
        asMultipleChoiceItem() { return this; }, asCheckboxItem() { return this; }, asPageBreakItem() { return this; },
        setChoiceValues(v) { this.choices = v.map(value => ({ value })); return this; }, showOtherOption(o) { this.other = o; return this; },
        createChoice: (value, page) => ({ value, page }), setChoices(c) { this.choices = c; return this; },
      };
    }
    form.makeItem = makeItem;
    forms[id] = form;
    return form;
  }
  if (props.FORM_ID) {
    const f = makeForm(props.FORM_ID, 'Other charity website content');
    formItems.forEach(([iid, type, title]) => f.items.push(f.makeItem(iid, type, title)));
    addFile(props.FORM_ID, 'form', 'form');
    setup(f);
  }

  const store = Object.assign({}, props);
  const driveCalls = [];
  const ctx = {
    SpreadsheetApp: {
      getActive: () => ss, flush() {},
      getUi: () => ({ alert(m) { alert = m; }, createMenu: () => chain() }),
      newDataValidation: chain, newConditionalFormatRule: chain,
    },
    FormApp: {
      ItemType, DestinationType: { SPREADSHEET: 'S' }, PageNavigationType: { CONTINUE: 'C', SUBMIT: 'S' },
      create(title) { const id = 'form' + nextId++; const f = makeForm(id, title); addFile(id, 'form', 'form'); return f; },
      openById(id) { if (!forms[id]) throw new Error('no form'); return forms[id]; },
    },
    DriveApp: { getFileById(id) { if (!files[id]) throw new Error('no file ' + id); return files[id]; } },
    Drive: {
      Files: {
        update(res, id, blob) { driveCalls.push(['update', id, blob.text]); return { id }; },
        create(res, blob) { driveCalls.push(['create', res.name, blob.text]); return { id: 'newdoc' }; },
      },
    },
    MimeType: { GOOGLE_DOCS: 'application/vnd.google-apps.document' },
    PropertiesService: { getDocumentProperties: () => ({
      getProperty: k => (k in store ? store[k] : null), setProperty(k, v) { store[k] = v; }, deleteProperty(k) { delete store[k]; },
    }) },
    LockService: { getDocumentLock: () => ({ tryLock: () => true, waitLock() {}, releaseLock() {} }) },
    ScriptApp: { getProjectTriggers: () => [], newTrigger: () => chain() },
    Utilities: { parseCsv },
    Logger: { log() {} },
  };
  vm.createContext(ctx);
  vm.runInContext(SCRIPT, ctx);
  return { ctx, requirements, sheets, forms, store, files, driveCalls, getAlert: () => alert };
}

module.exports = { makeWorld, parseCsv, CSV };
