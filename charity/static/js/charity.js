// "Copy link" buttons: <button data-copy="input-id" hidden> copies that input's value.
// Buttons stay hidden without JavaScript; visitors can still select the text themselves.
document.querySelectorAll("[data-copy]").forEach((button) => {
    const input = document.getElementById(button.dataset.copy);
    const status = document.querySelector(`[data-copy-status="${button.dataset.copy}"]`);

    button.hidden = false;
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(input.value);
            status.textContent = "Link copied. Paste it into your news reader app.";
        } catch {
            // Clipboard access can be blocked (e.g. on plain http); select the text instead.
            input.select();
            status.textContent = "Press Ctrl+C (or ⌘+C) to copy the selected link.";
        }
    });
});
