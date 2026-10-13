/**
 * Content tracker for one charity: keeps the Requirements tab and the guide Doc up to date
 * from the pack (onboarding/ in the repo), builds the Google Form from Requirements, and
 * marks each requirement "Received" when the charity answers it.
 *
 * The same script serves every charity. It works on the Sheet it's bound to and the folder
 * that Sheet is in (Charities/<domain>/), and names the form and guide after the Sheet:
 * "CCDCE content tracker" builds "CCDCE website content" and "CCDCE website guide".
 *
 * Setup (once per Sheet): Extensions > Apps Script, paste this file, save; in the editor,
 * Services (+) > Drive API > Add. Reload the Sheet and use the "Website form" menu.
 *
 * Update from the pack: upload the filled-in guide.md and questions.csv to the folder, then
 * run "Update from the pack". It merges questions.csv into Requirements by ID (answers and
 * statuses are kept), rewrites the guide Doc in place (its link never changes), and rebuilds
 * the form.
 *
 * Upload questions: Apps Script cannot create them, so rows with Answer type "upload" are
 * added by hand in the Forms editor, with the exact Question text from the row. The next
 * build finds them by that text, moves them into place and tracks them. Uploads are never
 * deleted by the script.
 */

const TAB = 'Requirements';
const PACK_COLUMNS = ['ID', 'Step', 'Section', 'Question', 'Help', 'Answer type', 'Options', 'In form', 'Owner', 'Notes'];
const TRACKER_COLUMNS = ['Status', 'Answers', 'Last answer', 'Date asked', 'Form item ID'];

const FORM_DESCRIPTION = [
  'Use this form to send us the words, photos and decisions for your website. You don\'t need everything at once: choose one part, fill in what you have, and submit. Come back and send more whenever the next part is ready. Every question is optional. Write in Nepali; add English too if you can. Google asks you to sign in with your Gmail account so that you can upload photos.',
  'तपाईंको वेबसाइटका लागि शब्द, फोटो र निर्णयहरू यो फारमबाट पठाउनुहोस्। सबै एकैपटक चाहिँदैन: एउटा भाग छान्नुहोस्, भएको कुरा भर्नुहोस्, र पठाउनुहोस्। अर्को भाग तयार भएपछि जुनसुकै बेला फेरि आएर पठाउनुहोस्। सबै प्रश्न ऐच्छिक छन्। नेपालीमा लेख्नुहोस्; सक्नुहुन्छ भने अंग्रेजीमा पनि। फोटो अपलोड गर्न Google ले तपाईंको Gmail खाताबाट साइन इन गर्न भन्छ।',
].join('\n\n');
const CONFIRMATION = 'Thank you, we have received it. To send another part, open the form again.\n'
  + 'धन्यवाद, हामीले पायौं। अर्को भाग पठाउन फारम फेरि खोल्नुहोस्।';
const MENU_TITLE = 'Which part are you sending today? / आज कुन भाग पठाउँदै हुनुहुन्छ?';

const PHOTO_OPTIONS = [
  'Sent on WhatsApp as a Document / WhatsApp मा Document को रूपमा पठायौं',
  'Sent on Google Drive / Google Drive मा पठायौं',
  'We will send it later / पछि पठाउँछौं',
];
const PHOTO_HELP = 'Send photos as files, not in a chat. In the message, write who took each photo and whether everyone in it agreed to be shown.\n'
  + 'फोटो फाइलको रूपमा पठाउनुहोस्। सन्देशमा हरेक फोटो कसले खिचेको र फोटोमा भएका सबै देखाउन सहमत छन् कि छैनन् लेख्नुहोस्।';

const UPLOAD_HELP = 'Upload the original photo from your phone (not a screenshot), in good light and not blurry.\n'
  + 'फोनबाट मूल फोटो अपलोड गर्नुहोस् (स्क्रिनसट होइन), उज्यालोमा खिचेको र धमिलो नभएको।';

const STATUSES = ['Not asked', 'Asked', 'Received', 'Approved', 'Not needed'];
const STATUS_COLOURS = {
  'Not asked': '#eeeeee', 'Asked': '#fff2cc', 'Received': '#cfe2f3', 'Approved': '#d9ead3', 'Not needed': '#f4cccc',
};
const TYPES = ['short', 'long', 'choice', 'checkboxes', 'photo', 'upload'];

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Website form')
    .addItem('Update from the pack', 'updateFromPack')
    .addItem('Build or update the form', 'buildForm')
    .addItem('Mark form questions as asked today', 'markAsked')
    .addItem('Refresh statuses now', 'refreshStatuses')
    .addToUi();
}

/* ---------- Names and places ---------- */

/** "CCDCE content tracker" -> "CCDCE": the short name the form and guide are named after. */
function shortName_(ss) {
  return ss.getName().replace(/\s*content tracker\s*$/i, '').trim();
}

function formTitle_(ss) {
  return shortName_(ss) + ' website content / वेबसाइटका लागि सामग्री';
}

function guideName_(ss) {
  return shortName_(ss) + ' website guide';
}

function folder_(ss) {
  return DriveApp.getFileById(ss.getId()).getParents().next();
}

/** The newest file with this name in the folder; older copies are moved to the bin. */
function newestFile_(folder, name) {
  const files = [];
  const it = folder.getFilesByName(name);
  while (it.hasNext()) files.push(it.next());
  if (files.length === 0) return null;
  files.sort((a, b) => b.getDateCreated() - a.getDateCreated());
  files.slice(1).forEach(f => f.setTrashed(true));
  return files[0];
}

function guideDoc_(ss) {
  const it = folder_(ss).getFilesByName(guideName_(ss));
  while (it.hasNext()) {
    const f = it.next();
    if (f.getMimeType() === MimeType.GOOGLE_DOCS && !f.isTrashed()) return f;
  }
  return null;
}

/* ---------- Reading the Requirements tab ---------- */

function requirementsSheet_() {
  const ss = SpreadsheetApp.getActive();
  let sheet = ss.getSheetByName(TAB);
  if (!sheet) {
    sheet = ss.getSheets()[0];
    sheet.setName(TAB);
  }
  return sheet;
}

function readTable_(sheet) {
  const values = sheet.getDataRange().getValues();
  const header = values[0].map(String);
  const col = {};
  header.forEach((name, i) => { col[name.trim()] = i; });
  PACK_COLUMNS.concat(TRACKER_COLUMNS).forEach(name => {
    if (!(name in col)) throw new Error('Column "' + name + '" is missing from ' + TAB + '.');
  });
  const rows = values.slice(1).map((v, i) => ({ v: v, sheetRow: i + 2 }))
    .filter(r => String(r.v[col['ID']]).trim() !== '');
  return { col: col, rows: rows, width: header.length };
}

function cell_(row, col, name) {
  return String(row.v[col[name]]).trim();
}

/* ---------- Updating from the pack ---------- */

function updateFromPack() {
  const ss = SpreadsheetApp.getActive();
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(1000)) {
    ss.toast('The form is already being built. Wait for it to finish.', 'Website form', 10);
    return;
  }
  try {
    const report = [mergeQuestions_(ss), updateGuide_(ss)];
    buildForm_(ss, report.join('\n\n'));
  } finally {
    lock.releaseLock();
  }
}

/** Merges questions.csv into Requirements by ID, keeping what the tracker has recorded. */
function mergeQuestions_(ss) {
  const file = newestFile_(folder_(ss), 'questions.csv');
  if (!file) throw new Error('Upload questions.csv to this Sheet\'s folder first.');
  const csv = Utilities.parseCsv(file.getBlob().getDataAsString('UTF-8'));
  const header = csv[0].map(s => String(s).trim());
  PACK_COLUMNS.forEach(name => {
    if (header.indexOf(name) < 0) throw new Error('questions.csv has no "' + name + '" column.');
  });
  const pack = csv.slice(1).filter(r => String(r[header.indexOf('ID')]).trim() !== '').map(r => {
    const row = {};
    header.forEach((name, i) => { row[name] = r[i]; });
    return row;
  });

  const sheet = requirementsSheet_();
  const t = readTable_(sheet);
  const col = t.col;
  const existing = {};
  t.rows.forEach(r => { existing[cell_(r, col, 'ID')] = r; });

  const out = [];
  const counts = { added: 0, updated: 0, removed: 0, kept: 0 };
  const inPack = {};
  pack.forEach(p => {
    inPack[p['ID']] = true;
    const old = existing[p['ID']];
    const v = old ? old.v.slice() : new Array(t.width).fill('');
    PACK_COLUMNS.forEach(name => { v[col[name]] = p[name]; });
    if (!old) v[col['Status']] = 'Not asked';
    counts[old ? 'updated' : 'added'] += 1;
    out.push(v);
  });
  // A question gone from the pack is dropped, unless the charity already answered it:
  // then it stays, out of the form, so the answer isn't lost.
  t.rows.forEach(r => {
    if (inPack[cell_(r, col, 'ID')]) return;
    if (cell_(r, col, 'Answers') === '' && ['Received', 'Approved'].indexOf(cell_(r, col, 'Status')) < 0) {
      counts.removed += 1;
      return;
    }
    const v = r.v.slice();
    v[col['In form']] = 'No';
    out.push(v);
    counts.kept += 1;
  });

  if (t.rows.length) sheet.getRange(2, 1, t.rows.length, t.width).clearContent();
  if (out.length) sheet.getRange(2, 1, out.length, t.width).setValues(out);
  return 'Questions: ' + counts.added + ' added, ' + counts.updated + ' updated, ' + counts.removed + ' removed'
    + (counts.kept ? ', ' + counts.kept + ' answered earlier and kept out of the form' : '') + '.';
}

/** Rewrites the guide Doc from guide.md, keeping its link; creates it the first time. */
function updateGuide_(ss) {
  const folder = folder_(ss);
  const file = newestFile_(folder, 'guide.md');
  if (!file) return 'Guide: no guide.md in the folder, so the guide was not changed.';
  if (typeof Drive === 'undefined') {
    throw new Error('Turn on the Drive API first: Extensions > Apps Script > Services (+) > Drive API > Add.');
  }
  const blob = file.getBlob().setContentType('text/markdown');
  const doc = guideDoc_(ss);
  if (doc) {
    Drive.Files.update({}, doc.getId(), blob);
    return 'Guide: updated (same link): ' + doc.getUrl();
  }
  const created = Drive.Files.create(
    { name: guideName_(ss), mimeType: MimeType.GOOGLE_DOCS, parents: [folder.getId()] }, blob);
  return 'Guide: created: https://docs.google.com/document/d/' + created.id + '/edit';
}

/* ---------- Building the form ---------- */

function buildForm() {
  const ss = SpreadsheetApp.getActive();
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(1000)) {
    ss.toast('The form is already being built. Wait for it to finish.', 'Website form', 10);
    return;
  }
  try {
    buildForm_(ss, '');
  } finally {
    lock.releaseLock();
  }
}

function buildForm_(ss, report) {
  ss.toast('Building the form. This takes 1–2 minutes: keep this tab open.', 'Website form', -1);
  const sheet = requirementsSheet_();
  const props = PropertiesService.getDocumentProperties();
  const t = readTable_(sheet);
  const col = t.col;

  let form = openForm_();
  if (!form) {
    form = FormApp.create(formTitle_(ss));
    props.setProperty('FORM_ID', form.getId());
    props.setProperty('SHEET_ID', ss.getId());
    props.deleteProperty('MENU_ID');
    props.deleteProperty('PAGE_IDS');
  }
  // Each step checks its own state, so a run that was stopped halfway is finished by the next one.
  const folder = folder_(ss);
  const formFile = DriveApp.getFileById(form.getId());
  if (!formFile.getParents().hasNext() || formFile.getParents().next().getId() !== folder.getId()) {
    formFile.moveTo(folder);
  }
  let destination = null;
  try { destination = form.getDestinationId(); } catch (e) { /* no destination yet */ }
  if (destination !== ss.getId()) form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  const guide = guideDoc_(ss);
  form.setTitle(formTitle_(ss))
    .setDescription(guide ? FORM_DESCRIPTION + '\n\nGuide / मार्गदर्शन: ' + guide.getUrl() : FORM_DESCRIPTION)
    .setConfirmationMessage(CONFIRMATION)
    .setShowLinkToRespondAgain(true)
    .setAllowResponseEdits(true)
    .setProgressBar(false);

  // Rows that belong in the form, grouped by section in sheet order.
  const sections = [];
  const bySection = {};
  t.rows.forEach(r => {
    if (cell_(r, col, 'In form').toLowerCase() !== 'yes') return;
    const type = cell_(r, col, 'Answer type').toLowerCase();
    if (TYPES.indexOf(type) < 0) {
      throw new Error('Row ' + r.sheetRow + ': Answer type must be one of ' + TYPES.join(', ') + '.');
    }
    const section = cell_(r, col, 'Section');
    if (!bySection[section]) { bySection[section] = []; sections.push(section); }
    bySection[section].push(r);
  });

  // The first question picks the part; each part ends by submitting.
  let menuItem = itemById_(form, props.getProperty('MENU_ID'));
  if (!menuItem || menuItem.getType() !== FormApp.ItemType.MULTIPLE_CHOICE) {
    if (menuItem) form.deleteItem(menuItem);
    menuItem = generic_(form, form.addMultipleChoiceItem());
    props.setProperty('MENU_ID', String(menuItem.getId()));
  }
  const menu = menuItem.asMultipleChoiceItem();
  menu.setTitle(MENU_TITLE).setRequired(true);

  const pageIds = JSON.parse(props.getProperty('PAGE_IDS') || '{}');
  const keep = {};
  keep[menu.getId()] = true;
  const order = [menu.getId()];
  const pages = [];
  const missingUploads = [];

  sections.forEach((section, i) => {
    ss.toast('Part ' + (i + 1) + ' of ' + sections.length + ': ' + section, 'Website form', -1);
    let page = itemById_(form, pageIds[section]);
    if (!page || page.getType() !== FormApp.ItemType.PAGE_BREAK) {
      page = generic_(form, form.addPageBreakItem());
      pageIds[section] = String(page.getId());
    }
    page.setTitle(section);
    keep[page.getId()] = true;
    order.push(page.getId());
    pages.push(page.asPageBreakItem());

    bySection[section].forEach(r => {
      const isUpload = cell_(r, col, 'Answer type').toLowerCase() === 'upload';
      const item = isUpload ? findUpload_(form, r, col) : upsertItem_(form, r, col);
      if (!item) {
        // Options is "3" (photos) or "5; PDF or photos".
        const options = cell_(r, col, 'Options').split(';').map(s => s.trim());
        const files = options[0] || '1';
        const kinds = options[1] || 'images only';
        missingUploads.push('• ' + section + ':\n   ' + cell_(r, col, 'Question')
          + '\n   (' + kinds + ', up to ' + files + ' file(s), 10 MB)');
        return;
      }
      keep[item.getId()] = true;
      order.push(item.getId());
      sheet.getRange(r.sheetRow, col['Form item ID'] + 1).setValue(String(item.getId()));
    });
  });
  Object.keys(pageIds).forEach(s => { if (sections.indexOf(s) < 0) delete pageIds[s]; });
  props.setProperty('PAGE_IDS', JSON.stringify(pageIds));

  menu.setChoices(pages.map((page, i) => menu.createChoice(sections[i], page)));
  // A page break's setting decides where the page before it goes: submit after each part.
  pages.forEach((page, i) => {
    page.setGoToPage(i === 0 ? FormApp.PageNavigationType.CONTINUE : FormApp.PageNavigationType.SUBMIT);
  });

  // Remove questions whose rows were deleted or taken out of the form, and parts the pack no
  // longer has (only now that the menu no longer goes to them: Forms won't delete a page a
  // choice goes to). Uploads can't be recreated by a script, so those are only reported.
  const strayUploads = [];
  form.getItems().forEach(item => {
    if (keep[item.getId()]) return;
    if (item.getType() === FormApp.ItemType.FILE_UPLOAD) strayUploads.push('• ' + item.getTitle());
    else form.deleteItem(item);
  });
  t.rows.forEach(r => {
    if (cell_(r, col, 'In form').toLowerCase() !== 'yes' && cell_(r, col, 'Form item ID')) {
      sheet.getRange(r.sheetRow, col['Form item ID'] + 1).setValue('');
    }
  });

  order.forEach((id, index) => {
    const item = form.getItemById(id);
    if (item.getIndex() !== index) form.moveItem(item, index);
  });

  ensureTrigger_(form);
  nameResponsesTab_(ss, form);
  formatSheet_(sheet, col);
  refreshStatuses_();
  writeLinks_(ss, form, guide);

  let message = (report ? report + '\n\n' : '')
    + 'The form is ready. The links are also in the "Form links" tab.\n\nLink to send: '
    + form.getPublishedUrl() + '\n\nEdit the form: ' + form.getEditUrl();
  if (missingUploads.length) {
    message += '\n\nAdd these upload questions by hand in the form editor (any section; the next build moves them), '
      + 'copying each title from the Question column of the Sheet, then run "Build or update the form" again:\n\n' + missingUploads.join('\n');
  }
  if (strayUploads.length) {
    message += '\n\nThese upload questions match no row in the Sheet. Fix the title, or delete them in the form editor:\n'
      + strayUploads.join('\n');
  }
  ss.toast('Done.', 'Website form', 5);
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (e) {
    Logger.log(message); // run from the script editor, where pop-ups can't open
  }
}

function writeLinks_(ss, form, guide) {
  const tab = ss.getSheetByName('Form links') || ss.insertSheet('Form links');
  const rows = [
    ['Link to send', form.getPublishedUrl()],
    ['Edit the form', form.getEditUrl()],
    ['Guide to send', guide ? guide.getUrl() : ''],
  ];
  tab.getRange(1, 1, rows.length, 2).setValues(rows);
  tab.getRange(1, 1, rows.length, 1).setFontWeight('bold');
  tab.setColumnWidth(1, 140);
}

/** Finds a hand-made upload question: by its saved ID, or by the row's exact Question text. */
function findUpload_(form, r, col) {
  let item = itemById_(form, cell_(r, col, 'Form item ID'));
  if (!item || item.getType() !== FormApp.ItemType.FILE_UPLOAD) {
    const title = cell_(r, col, 'Question');
    item = form.getItems(FormApp.ItemType.FILE_UPLOAD).filter(i => i.getTitle().trim() === title)[0] || null;
  }
  if (!item) return null;
  const help = cell_(r, col, 'Help');
  try {
    item.setHelpText(help ? help + '\n\n' + UPLOAD_HELP : UPLOAD_HELP);
  } catch (e) {
    // Some accounts don't allow scripts to edit upload questions; the help text then stays as typed.
  }
  return item;
}

function upsertItem_(form, r, col) {
  const type = cell_(r, col, 'Answer type').toLowerCase();
  const wanted = {
    short: FormApp.ItemType.TEXT,
    long: FormApp.ItemType.PARAGRAPH_TEXT,
    choice: FormApp.ItemType.MULTIPLE_CHOICE,
    photo: FormApp.ItemType.MULTIPLE_CHOICE,
    checkboxes: FormApp.ItemType.CHECKBOX,
  }[type];

  let item = itemById_(form, cell_(r, col, 'Form item ID'));
  if (item && item.getType() !== wanted) { form.deleteItem(item); item = null; }
  if (!item) {
    item = generic_(form, {
      short: () => form.addTextItem(),
      long: () => form.addParagraphTextItem(),
      choice: () => form.addMultipleChoiceItem(),
      photo: () => form.addMultipleChoiceItem(),
      checkboxes: () => form.addCheckboxItem(),
    }[type]());
  }

  let help = cell_(r, col, 'Help');
  if (type === 'photo') help = help ? help + '\n\n' + PHOTO_HELP : PHOTO_HELP;
  item.setTitle(cell_(r, col, 'Question')).setHelpText(help);

  if (type === 'choice' || type === 'photo' || type === 'checkboxes') {
    let options = cell_(r, col, 'Options').split('|').map(s => s.trim()).filter(Boolean);
    if (type === 'photo' && options.length === 0) options = PHOTO_OPTIONS;
    const other = options.length > 0 && options[options.length - 1].toLowerCase() === 'other';
    if (other) options.pop();
    if (options.length === 0) throw new Error('Row ' + r.sheetRow + ': add Options for this question.');
    const typed = type === 'checkboxes' ? item.asCheckboxItem() : item.asMultipleChoiceItem();
    typed.setChoiceValues(options).showOtherOption(other);
  }
  return item;
}

/** add*Item() returns a typed item without the as*Item() methods; this gives back the plain Item that has them. */
function generic_(form, typedItem) {
  return form.getItemById(typedItem.getId());
}

function itemById_(form, id) {
  if (!id) return null;
  try { return form.getItemById(Number(id)); } catch (e) { return null; }
}

/**
 * The form this Sheet built. A Sheet copied from another charity's tracker may carry that
 * tracker's settings, so a form recorded by a different Sheet is never reused.
 */
function openForm_() {
  const props = PropertiesService.getDocumentProperties();
  const id = props.getProperty('FORM_ID');
  if (!id) return null;
  const sheetId = SpreadsheetApp.getActive().getId();
  const builtBy = props.getProperty('SHEET_ID');
  if (builtBy && builtBy !== sheetId) return null;
  try {
    if (DriveApp.getFileById(id).isTrashed()) return null; // a trashed form still opens; start a new one
    const form = FormApp.openById(id);
    if (!builtBy) props.setProperty('SHEET_ID', sheetId); // trackers made before SHEET_ID was recorded
    return form;
  } catch (e) {
    return null;
  }
}

function ensureTrigger_(form) {
  const exists = ScriptApp.getProjectTriggers().some(tr =>
    tr.getHandlerFunction() === 'refreshStatuses' && tr.getTriggerSourceId() === form.getId());
  if (!exists) ScriptApp.newTrigger('refreshStatuses').forForm(form).onFormSubmit().create();
}

function nameResponsesTab_(ss, form) {
  SpreadsheetApp.flush();
  ss.getSheets().forEach(sh => {
    const url = sh.getFormUrl();
    if (url && url.indexOf(form.getId()) >= 0 && sh.getName() !== 'Responses' && !ss.getSheetByName('Responses')) {
      sh.setName('Responses');
    }
  });
}

/**
 * Layout only. A Sheets table (Format > Convert to table) refuses dropdowns, number
 * formats and filters on its typed columns and has its own, so each step is
 * skipped when the sheet refuses it.
 */
function formatSheet_(sheet, col) {
  const lastRow = Math.max(sheet.getLastRow(), 2);
  const lastCol = sheet.getLastColumn();
  const n = sheet.getMaxRows() - 1;
  const colRange = (name) => sheet.getRange(2, col[name] + 1, n, 1);
  const rule = (list, strict) => SpreadsheetApp.newDataValidation()
    .requireValueInList(list, true).setAllowInvalid(!strict).build();

  tryStep_(() => sheet.setFrozenRows(1));
  tryStep_(() => sheet.setFrozenColumns(1));
  tryStep_(() => sheet.getRange(1, 1, 1, lastCol).setFontWeight('bold').setBackground('#d9d9d9'));
  tryStep_(() => sheet.getRange(2, 1, lastRow - 1, lastCol).setVerticalAlignment('top'));
  [['Question', 360], ['Help', 360], ['Options', 260], ['Section', 200], ['Notes', 220]].forEach(([name, width]) => {
    tryStep_(() => sheet.setColumnWidth(col[name] + 1, width));
    tryStep_(() => sheet.getRange(2, col[name] + 1, lastRow - 1, 1).setWrap(true));
  });
  tryStep_(() => colRange('Status').setDataValidation(rule(STATUSES, true)));
  tryStep_(() => colRange('In form').setDataValidation(rule(['Yes', 'No'], true)));
  tryStep_(() => colRange('Answer type').setDataValidation(rule(TYPES, false)));
  tryStep_(() => colRange('Last answer').setNumberFormat('yyyy-mm-dd hh:mm'));
  tryStep_(() => colRange('Date asked').setNumberFormat('yyyy-mm-dd'));
  tryStep_(() => {
    const statusRange = colRange('Status');
    const others = sheet.getConditionalFormatRules().filter(r =>
      !r.getRanges().some(rg => rg.getColumn() === col['Status'] + 1));
    const colourRules = STATUSES.map(s => SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(s).setBackground(STATUS_COLOURS[s]).setRanges([statusRange]).build());
    sheet.setConditionalFormatRules(others.concat(colourRules));
  });
  tryStep_(() => { if (!sheet.getFilter()) sheet.getRange(1, 1, lastRow, lastCol).createFilter(); });
}

function tryStep_(step) {
  try {
    step();
  } catch (e) {
    Logger.log('Skipped a formatting step: ' + e.message);
  }
}

/* ---------- Tracking ---------- */

/** Recounts every answer from the form, so edits and deleted responses stay correct. */
function refreshStatuses() {
  const lock = LockService.getDocumentLock();
  lock.waitLock(300000); // a build may be running; it refreshes too, so waiting is safe
  try {
    refreshStatuses_();
  } finally {
    lock.releaseLock();
  }
}

function refreshStatuses_() {
  const form = openForm_();
  if (!form) return;
  const stats = {};
  form.getResponses().forEach(resp => {
    const when = resp.getTimestamp();
    resp.getItemResponses().forEach(ir => {
      const a = ir.getResponse();
      const empty = a === null || (Array.isArray(a) ? a.length === 0 : String(a).trim() === '');
      if (empty) return;
      const id = String(ir.getItem().getId());
      const s = stats[id] || (stats[id] = { count: 0, last: null });
      s.count += 1;
      if (!s.last || when > s.last) s.last = when;
    });
  });

  const sheet = requirementsSheet_();
  const t = readTable_(sheet);
  const col = t.col;
  t.rows.forEach(r => {
    const id = cell_(r, col, 'Form item ID');
    if (!id || cell_(r, col, 'In form').toLowerCase() !== 'yes') return;
    const s = stats[id];
    const status = cell_(r, col, 'Status');
    let next = status;
    if (s && (status === 'Not asked' || status === 'Asked' || status === '')) next = 'Received';
    if (!s && status === 'Received') next = 'Asked';
    const answers = s ? s.count : '';
    const last = s ? s.last : '';
    if (next !== status) sheet.getRange(r.sheetRow, col['Status'] + 1).setValue(next);
    if (String(r.v[col['Answers']]) !== String(answers)) sheet.getRange(r.sheetRow, col['Answers'] + 1).setValue(answers);
    sheet.getRange(r.sheetRow, col['Last answer'] + 1).setValue(last);
  });
}

/** Run when you send the form link: every form question not yet asked becomes "Asked" today. */
function markAsked() {
  const sheet = requirementsSheet_();
  const t = readTable_(sheet);
  const col = t.col;
  const today = new Date();
  t.rows.forEach(r => {
    if (cell_(r, col, 'In form').toLowerCase() !== 'yes') return;
    if (cell_(r, col, 'Status') !== 'Not asked') return;
    sheet.getRange(r.sheetRow, col['Status'] + 1).setValue('Asked');
    sheet.getRange(r.sheetRow, col['Date asked'] + 1).setValue(today);
  });
}
