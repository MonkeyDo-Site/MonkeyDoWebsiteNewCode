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
        const options = [new Option('Select a customer from the search results', '')];
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
const bookingSearch = document.querySelector('#booking-filter-form') && document.querySelector('#id_q');
if (bookingSearch) bookingSearch.addEventListener('keydown', event => {
  if (event.key === 'Enter') { event.preventDefault(); document.querySelector('#booking-filter-form').requestSubmit(); }
});
for (const form of document.querySelectorAll('form[data-booking-estimate]')) {
  const content = form.querySelector('[data-estimate-content]');
  const status = form.querySelector('[data-estimate-status]');
  const dialog = document.querySelector('.payment-reminder');
  let timer, controller, saving = false, lastEstimate;
  async function refresh() {
    if (controller) controller.abort();
    controller = new AbortController();
    status.textContent = 'Updating estimate…';
    try {
      const response = await fetch(form.dataset.bookingEstimate, {method: 'POST', body: new FormData(form), signal: controller.signal, headers: {Accept: 'application/json'}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Could not update the estimate. Refresh this page and try again.');
      const data = await response.json();
      if (!response.ok) {
        const errors = data.error || Object.values(data.errors || {}).flat().map(item => item.message).join(' ');
        throw new Error(errors || 'Review the booking fields.');
      }
      content.innerHTML = data.html;
      status.textContent = 'Updated estimate: $' + data.total + '. Not saved yet.';
      lastEstimate = data;
      return data;
    } catch (error) {
      if (error.name !== 'AbortError') { status.textContent = error.message; lastEstimate = null; }
      return null;
    }
  }
  form.addEventListener('input', event => {
    if (event.target.name === 'estimate_token') return;
    form.querySelector('[name=estimate_token]').value = '';
    clearTimeout(timer); timer = setTimeout(refresh, 250);
  });
  form.addEventListener('change', () => { clearTimeout(timer); timer = setTimeout(refresh, 100); });
  form.addEventListener('submit', async event => {
    if (saving) return;
    event.preventDefault(); clearTimeout(timer);
    const data = await refresh();
    if (!data) return;
    if (data.amount_changed) {
      dialog.querySelector('[data-reminder-amount]').textContent = 'The revised amount is $' + data.total + ' (previously $' + data.original_total + ').';
      dialog.showModal();
    } else { saving = true; form.requestSubmit(); }
  });
  dialog.querySelector('[data-review-method]').addEventListener('click', () => { dialog.close(); form.querySelector('[name=expected_method]').focus(); });
  dialog.querySelector('[data-save-edit]').addEventListener('click', () => {
    if (!lastEstimate) return;
    form.querySelector('[name=estimate_token]').value = lastEstimate.token;
    dialog.close(); saving = true; form.requestSubmit();
  });
}
