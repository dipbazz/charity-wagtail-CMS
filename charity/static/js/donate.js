// Scripts for the Donate page and its pay pages only, so other pages don't download them (page
// weight budgets in lighthouserc.json). Loaded after charity.js by their templates.

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

// Pay buttons (the pay page's, and "Continue to eSewa"): the provider's page can take seconds on a
// slow connection, so the pressed button says it's opening, all of them stop taking taps (a second
// tap would start a second payment), and a status line tells screen readers. A page restored from
// the browser's cache, by Back from the provider, gets working buttons again. Without JavaScript,
// the buttons just send their form.
const busyButtons = [...document.querySelectorAll("button[data-busy-text]")];
if (busyButtons.length) {
    const status = document.querySelector("[data-busy-status]");
    const groups = new Set(busyButtons.map((button) => button.closest(".payment-options")));
    const labels = new Map(busyButtons.map((button) => [button, button.textContent]));
    let busy = false;
    for (const button of busyButtons) {
        button.form.addEventListener("submit", (event) => {
            if (busy) {
                event.preventDefault();
                return;
            }
            busy = true;
            const pressed = event.submitter ?? button;
            pressed.textContent = pressed.dataset.busyText;
            if (status) status.textContent = pressed.dataset.busyText;
            groups.forEach((group) => group?.setAttribute("aria-busy", "true"));
            busyButtons.forEach((other) => (other.disabled = true));
        });
    }
    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        busy = false;
        for (const [button, label] of labels) {
            button.textContent = label;
            button.disabled = false;
        }
        groups.forEach((group) => group?.removeAttribute("aria-busy"));
        if (status) status.textContent = "";
    });
}

// The pay page's message, what became of paying (didn't go through, check first, thank you):
// focused as the page opens, so a screen reader reads it before the rest of the page.
document.querySelector("[data-focus-on-load]")?.focus();

// Paying with a provider that takes a posted form (eSewa): the page holds the form the server
// signed, and this sends it at once. Not when the page is reached with Back or Forward, so the
// payer can leave it; and without JavaScript, they press its button.
const providerForm = document.querySelector("form[data-auto-submit]");
if (providerForm) {
    const [navigation] = performance.getEntriesByType("navigation");
    if (navigation?.type !== "back_forward") {
        providerForm.submit();
    }
    // Back from a provider that takes its form only once (eSewa), restored from the browser's
    // cache: fetched again instead, so the server sends the payer to the pay page rather than
    // offer a form the provider would refuse.
    if (providerForm.hasAttribute("data-sent-once")) {
        window.addEventListener("pageshow", (event) => {
            if (event.persisted) window.location.reload();
        });
    }
}
