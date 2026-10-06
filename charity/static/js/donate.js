// Scripts for the Donate page only, so other pages don't download them (page weight budgets in
// lighthouserc.json). Loaded after charity.js by donate_page.html.

// Pledge form: each copy has a one-time ID (submission_id), and sending a copy again updates its
// pledge instead of adding a second one. Going back from the thank-you page can reload the form
// with a new ID while the browser refills what was typed, so remember the ID that was sent in
// this tab and put it back when the form is reached with Back or Forward. Opening the Donate
// page any other way starts a new pledge. Without JavaScript, or storage, a resent copy may
// still be saved twice.
const pledgeForm = document.querySelector(".pledge-form");
if (pledgeForm) {
    const submissionId = pledgeForm.elements.submission_id;
    const key = `pledge-sent:${location.pathname}`;
    const [navigation] = performance.getEntriesByType("navigation");
    try {
        const sent = sessionStorage.getItem(key);
        if (sent && navigation?.type === "back_forward") {
            submissionId.value = sent;
        }
        pledgeForm.addEventListener("submit", () => sessionStorage.setItem(key, submissionId.value));
    } catch {
        // Storage can be blocked (some private windows); the form still works.
    }
}
