// Runs onboarding/form-script.gs against fake Apps Script services, one scenario at a time.
// Usage: node form_script_fakes.js <scenario>. test_form_script.py runs every scenario.
// The fakes keep the rules of the real services that the script has tripped on, such as
// Forms refusing to delete a page that a choice still goes to.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const PACK = path.join(__dirname, '..', '..', 'onboarding');
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

// A tracker built from an older pack: some rows and form items the pack no longer has.
const HEADER = ['ID', 'Step', 'Section', 'Question', 'Help', 'Answer type', 'Options', 'In form', 'Status', 'Answers', 'Last answer', 'Date asked', 'Owner', 'Notes', 'Form item ID'];
const CENTRE = 'Photos of your centre, classes or activities (1–3, optional) / केन्द्र, कक्षा वा गतिविधिका फोटो (१–३, ऐच्छिक)';
const OLD_PART = 'Old part / पुरानो भाग';
const oldRows = () => [
  ['H03', '1 Go live', 'Home page / गृहपृष्ठ', 'Slogan / नारा', '', 'short', '', 'Yes', 'Not asked', '', '', '', 'Charity', '', '11'],
  ['A05', '1 Go live', 'About us / हाम्रो बारेमा', CENTRE, '', 'upload', '3', 'Yes', 'Not asked', '', '', '', 'Charity', '', '12'],
  ['X99', '1 Go live', 'Home page / गृहपृष्ठ', 'Answered earlier / पहिले', '', 'long', '', 'Yes', 'Received', 1, '', '', 'Charity', '', '13'],
  ['DEV', '1 Go live', 'Our side', 'Developer row', '', 'short', '', 'No', 'Not asked', '', '', '', 'Us', '', ''],
];
const OLD_ITEMS = [
  [10, 'MULTIPLE_CHOICE', 'menu'], [11, 'TEXT', 'Slogan / नारा'], [12, 'FILE_UPLOAD', CENTRE],
  [13, 'PARAGRAPH_TEXT', 'Answered earlier / पहिले'], [14, 'FILE_UPLOAD', 'Your logo / तपाईंको लोगो'],
  [15, 'FILE_UPLOAD', 'Photo for this appeal / यस अपीलको फोटो'], [16, 'PAGE_BREAK', OLD_PART],
];
// The menu still goes to a part the pack no longer has.
const OLD_PROPS = { FORM_ID: 'form1', MENU_ID: '10', PAGE_IDS: JSON.stringify({ [OLD_PART]: '16' }) };
const menuGoesToOldPart = form => { form.items[0].choices = [{ value: OLD_PART, page: form.items[6] }]; };
const packIds = parseCsv(CSV).slice(1).map(r => r[0]);

const SCENARIOS = {
  'updates an existing tracker in place'() {
    const w = makeWorld({ props: OLD_PROPS, formItems: OLD_ITEMS, rows: oldRows(), header: HEADER, setup: menuGoesToOldPart });
    w.ctx.updateFromPack();
    const rows = w.requirements.values.slice(1).filter(r => r[0] !== '');
    const ids = rows.map(r => r[0]);
    assert.deepStrictEqual(ids, [...packIds, 'X99'], 'pack rows in order, then the answered row');
    const x99 = rows.find(r => r[0] === 'X99');
    assert.strictEqual(x99[7], 'No', 'an answered row gone from the pack leaves the form');
    assert.strictEqual(x99[9], 1, 'its answer count is kept');
    assert(!ids.includes('H03') && !ids.includes('DEV'), 'unanswered rows gone from the pack are removed');
    const form = w.forms.form1;
    assert.strictEqual(w.store.FORM_ID, 'form1', 'the same form is kept');
    assert.strictEqual(w.store.SHEET_ID, 'sheet1', 'a tracker made before SHEET_ID adopts its form');
    assert.strictEqual(form.title, 'Brightwell website content / वेबसाइटका लागि सामग्री');
    assert(form.description.includes('Guide / मार्गदर्शन: https://docs.google.com/document/d/doc1/edit'));
    assert.deepStrictEqual(w.driveCalls.map(c => c.slice(0, 2)), [['update', 'doc1']], 'guide rewritten in place');
    assert(w.driveCalls[0][2].includes('brightwell.example'));
    assert(w.files['csv-old'].trashed && !w.files.csv1.trashed, 'older questions.csv is binned');
    assert.strictEqual(String(rows.find(r => r[0] === 'AB11')[14]), '12', 'the hand-made upload is adopted by its title');
    assert.strictEqual(String(rows.find(r => r[0] === 'LF01')[14]), '14');
    assert(!form.items.some(i => i.id === 11), 'the old slogan question is deleted');
    assert(!form.items.some(i => i.id === 16), 'the old part is deleted');
    assert(form.items.some(i => i.id === 15), 'an upload is never deleted');
    const alert = w.getAlert();
    assert(alert.includes('Questions: '), alert);
    assert(alert.includes('PDF or photos, up to 5 file(s)'), 'upload kinds are passed on');
    assert(alert.includes('These upload questions match no row') && alert.includes('यस अपीलको फोटो'), 'stray upload reported');
    const sections = form.items[0].choices.map(c => c.value);
    // Arrays made in the script's own context are compared as JSON.
    assert.strictEqual(JSON.stringify(sections.slice(0, 3)), JSON.stringify(['Home page / गृहपृष्ठ', 'About us / हाम्रो बारेमा', 'Contact / सम्पर्क']));
    assert(!sections.includes('Our side') && !sections.includes(OLD_PART));
    const linkTab = w.sheets.find(s => s.name === 'Form links');
    assert.strictEqual(linkTab.values[2][1], 'https://docs.google.com/document/d/doc1/edit');
    rows.filter(r => r[7] === 'Yes').forEach(r => {
      if (r[5] === 'upload' && r[14] === '') return; // added by hand later
      assert(form.items.some(i => String(i.id) === String(r[14])), 'item for ' + r[0]);
    });
    const ws02 = form.items.find(i => i.title.startsWith('Dates:'));
    assert.strictEqual(JSON.stringify(ws02.choices.map(c => c.value)), JSON.stringify(['BS / वि.सं.', 'AD / ई.सं.', 'Both / दुवै']));
    const gi01 = form.items.find(i => i.title.startsWith('Which ways can people help'));
    assert.strictEqual(gi01.other, true, '"Other" becomes the other option');

    const created = form.created;
    w.ctx.updateFromPack();
    assert.strictEqual(form.created, created, 'a second run creates no new items');
  },

  'never edits the form of the tracker it was copied from'() {
    const w = makeWorld({ props: { ...OLD_PROPS, SHEET_ID: 'other-sheet' }, formItems: OLD_ITEMS, rows: [], header: HEADER, setup: menuGoesToOldPart });
    w.ctx.updateFromPack();
    assert.notStrictEqual(w.store.FORM_ID, 'form1', 'a new form is made');
    assert.strictEqual(w.forms.form1.title, 'Other charity website content', 'the other charity\'s form is untouched');
    assert.strictEqual(w.store.SHEET_ID, 'sheet1');
  },

  'creates the guide on a first run'() {
    const w = makeWorld({ rows: [], header: HEADER });
    w.files.doc1.trashed = true;
    w.ctx.updateFromPack();
    assert.deepStrictEqual(w.driveCalls.map(c => c.slice(0, 2)), [['create', 'Brightwell website guide']]);
  },
};

const name = process.argv[2];
if (!SCENARIOS[name]) {
  console.error('Scenarios:\n' + Object.keys(SCENARIOS).join('\n'));
  process.exit(2);
}
SCENARIOS[name]();
console.log('ok: ' + name);
