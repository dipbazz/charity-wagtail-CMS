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
