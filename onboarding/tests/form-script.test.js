// Tests for onboarding/form-script.gs, run against the fakes in fakes.js.
// Run: node --test onboarding/tests/form-script.test.js (CI runs it in its own step).
const test = require('node:test');
const assert = require('node:assert');
const { makeWorld, parseCsv, CSV } = require('./fakes');

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
// Arrays made in the script's own context are compared as JSON.
const sameList = (actual, expected) => assert.strictEqual(JSON.stringify(actual), JSON.stringify(expected));

test('updates an existing tracker in place', () => {
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
  sameList(sections.slice(0, 3), ['Home page / गृहपृष्ठ', 'About us / हाम्रो बारेमा', 'Contact / सम्पर्क']);
  assert(!sections.includes('Our side') && !sections.includes(OLD_PART));
  const linkTab = w.sheets.find(s => s.name === 'Form links');
  assert.strictEqual(linkTab.values[2][1], 'https://docs.google.com/document/d/doc1/edit');
  rows.filter(r => r[7] === 'Yes').forEach(r => {
    if (r[5] === 'upload' && r[14] === '') return; // added by hand later
    assert(form.items.some(i => String(i.id) === String(r[14])), 'item for ' + r[0]);
  });
  const ws02 = form.items.find(i => i.title.startsWith('Dates:'));
  sameList(ws02.choices.map(c => c.value), ['BS / वि.सं.', 'AD / ई.सं.', 'Both / दुवै']);
  const gi01 = form.items.find(i => i.title.startsWith('Which ways can people help'));
  assert.strictEqual(gi01.other, true, '"Other" becomes the other option');

  const created = form.created;
  w.ctx.updateFromPack();
  assert.strictEqual(form.created, created, 'a second run creates no new items');
});

test('never edits the form of the tracker it was copied from', () => {
  const w = makeWorld({ props: { ...OLD_PROPS, SHEET_ID: 'other-sheet' }, formItems: OLD_ITEMS, rows: [], header: HEADER, setup: menuGoesToOldPart });
  w.ctx.updateFromPack();
  assert.notStrictEqual(w.store.FORM_ID, 'form1', 'a new form is made');
  assert.strictEqual(w.forms.form1.title, 'Other charity website content', 'the other charity\'s form is untouched');
  assert.strictEqual(w.store.SHEET_ID, 'sheet1');
});

// Every charity's form is in the same Google account, so a copied tracker can open the other
// charity's form; without SHEET_ID, only the form's answer destination says whose it is.
test('never adopts the form of an older tracker it was copied from', () => {
  const w = makeWorld({ props: OLD_PROPS, formItems: OLD_ITEMS, formDestination: 'other-sheet', rows: [], header: HEADER, setup: menuGoesToOldPart });
  w.ctx.updateFromPack();
  assert.notStrictEqual(w.store.FORM_ID, 'form1', 'a new form is made');
  const other = w.forms.form1;
  assert.strictEqual(other.title, 'Other charity website content', 'the other charity\'s form is untouched');
  assert.strictEqual(other.destination, 'other-sheet', 'its answers still go to its own tracker');
  assert.strictEqual(w.store.SHEET_ID, 'sheet1');
});

test('creates the guide on a first run', () => {
  const w = makeWorld({ rows: [], header: HEADER });
  w.files.doc1.trashed = true;
  w.ctx.updateFromPack();
  assert.deepStrictEqual(w.driveCalls.map(c => c.slice(0, 2)), [['create', 'Brightwell website guide']]);
});
