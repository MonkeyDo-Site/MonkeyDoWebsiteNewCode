const staffMenu = document.querySelector('.staff-nav');
if (staffMenu) {
  const narrow = window.matchMedia('(max-width: 760px)');
  const adapt = () => { staffMenu.open = !narrow.matches; };
  adapt(); narrow.addEventListener('change', adapt);
}
/* Progressive enhancement: all authorization and validation stays server-side. */
for (const form of document.querySelectorAll('form[data-confirm]')) {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) { event.preventDefault(); return; }
    let confirmation = form.querySelector('input[name="confirm_cancel"]');
    if (!confirmation) {
      confirmation = document.createElement('input');
      confirmation.type = 'hidden'; confirmation.name = 'confirm_cancel';
      form.append(confirmation);
    }
    confirmation.value = '1';
  });
}
for (const input of document.querySelectorAll('[data-customer-search]')) {
  const form = input.closest('form');
  const select = form.querySelector('[data-customer-picker]');
  const status = form.querySelector('[data-picker-status]');
  if (!select) continue;
  let timer, controller;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    if (controller) controller.abort();
    if (input.value.trim().length < 2) { status.textContent = 'Type at least two characters.'; return; }
    timer = setTimeout(async () => {
      controller = new AbortController();
      status.textContent = 'Searching…';
      try {
        const response = await fetch('/staff/customers/search/?q=' + encodeURIComponent(input.value.trim()), {signal: controller.signal, headers: {Accept: 'application/json'}});
        if (!response.ok) throw new Error('Search unavailable');
        const data = await response.json();
        const selected = select.selectedOptions[0];
        const options = [new Option('Select a customer', '')];
        if (selected && selected.value && !data.results.some(row => String(row.id) === selected.value)) options.push(new Option(selected.text, selected.value, true, true));
        for (const row of data.results) options.push(new Option(row.text, row.id, false, selected?.value === String(row.id)));
        select.replaceChildren(...options);
        status.textContent = data.results.length ? data.results.length + ' matches. Choose a customer below.' : 'No customers found. Try another spelling or phone number.';
      } catch (error) {
        if (error.name !== 'AbortError') status.textContent = 'Search could not finish. Please try again.';
      }
    }, 250);
  });
}
