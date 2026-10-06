// "Copy link" buttons: <button data-copy="input-id" hidden> copies that input's value.
// Buttons stay hidden without JavaScript; visitors can still select the text themselves.
document.querySelectorAll("[data-copy]").forEach((button) => {
    const input = document.getElementById(button.dataset.copy);
    const status = document.querySelector(`[data-copy-status="${button.dataset.copy}"]`);

    const label = button.textContent;
    let resetTimer;

    button.hidden = false;
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(input.value);
            // Confirm on the button itself, where the visitor is looking. The tick is decorative;
            // screen readers get the status message below instead.
            button.textContent = "Copied ";
            button.insertAdjacentHTML("beforeend", '<span aria-hidden="true">✓</span>');
            clearTimeout(resetTimer);
            resetTimer = setTimeout(() => {
                button.textContent = label;
            }, 2000);
            status.textContent = "Link copied. Paste it into your news reader app.";
        } catch {
            // Clipboard access can be blocked (e.g. on plain http); select the text instead.
            input.select();
            status.textContent = "Press Ctrl+C (or ⌘+C) to copy the selected link.";
        }
    });
});

// Menu button: on narrow screens it opens and closes the menu and search (see charity.css).
// The CSS shows it only once base.html has marked the page with the "js" class; without
// JavaScript the menu stays open so every link can be reached.
const menuToggle = document.querySelector(".menu-toggle");
if (menuToggle) {
    const menu = document.getElementById(menuToggle.getAttribute("aria-controls"));
    const isOpen = () => menuToggle.getAttribute("aria-expanded") === "true";
    const setOpen = (open) => menuToggle.setAttribute("aria-expanded", String(open));

    menuToggle.addEventListener("click", () => setOpen(!isOpen()));
    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || !isOpen()) return;
        setOpen(false);
        // Focus would otherwise be left on a link that has just been hidden.
        if (menu.contains(document.activeElement)) menuToggle.focus();
    });
}

// Donate page: "Your own amount" is hidden unless "Other amount" is chosen (see charity.css), so
// clear it when a suggested amount is chosen; a forgotten hidden value would otherwise be sent
// and the form would ask the supporter to choose between two amounts.
const ownAmount = document.getElementById("id_other_amount");
if (ownAmount) {
    document.querySelectorAll('input[name="amount"]').forEach((radio) => {
        radio.addEventListener("change", () => {
            if (radio.checked && radio.value !== "other") {
                ownAmount.value = "";
            }
        });
        // Clicking or tapping "Other amount" goes straight to typing the amount. Arrow keys
        // through the choices also fire "click", with detail 0: keep focus on the choices then,
        // so keyboard users aren't pulled out of them; the field is the next Tab stop.
        if (radio.value === "other") {
            radio.addEventListener("click", (event) => {
                if (event.detail > 0) {
                    ownAmount.focus();
                }
            });
        }
    });
}

// Character counts: a textarea with data-char-count and a maxlength shows "10/1000 characters"
// below it, so a supporter who reaches the limit knows why typing stopped. From 95% of the limit
// (950 of 1000) the box and the count turn amber (.is-near-limit in charity.css). Screen readers
// hear only that and reaching the limit, through a hidden status message, not every keystroke.
// Without JavaScript there's no count, and maxlength still stops typing at the limit.
document.querySelectorAll("textarea[data-char-count][maxlength]").forEach((box) => {
    const limit = Number(box.getAttribute("maxlength"));
    const warnFrom = Math.ceil(limit * 0.95);

    const count = document.createElement("p");
    count.className = "char-count";
    count.setAttribute("aria-hidden", "true");
    const status = document.createElement("p");
    status.className = "visually-hidden";
    status.id = `${box.id}_count_status`;
    status.setAttribute("role", "status");
    box.after(count, status);

    let state;
    const update = () => {
        const typed = box.value.length;
        const near = typed >= warnFrom;
        count.textContent = `${typed}/${limit} characters`;
        count.classList.toggle("is-near-limit", near);
        box.classList.toggle("is-near-limit", near);

        const newState = typed >= limit ? "full" : near ? "near" : "ok";
        if (newState !== state) {
            state = newState;
            status.textContent = {
                ok: "",
                near: `You have ${limit - typed} characters left.`,
                full: `You've reached the limit of ${limit} characters.`,
            }[state];
        }
    };
    box.addEventListener("input", update);
    update();
});

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
