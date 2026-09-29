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
