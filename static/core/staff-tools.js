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
for (const details of document.querySelectorAll('.session-filter')) {
  const summary = details.querySelector('summary');
  const text = details.querySelector('[data-session-summary]');
  const panel = details.querySelector('.session-filter-options');
  const all = panel.querySelector('[data-all-sessions]');
  const options = [...panel.querySelectorAll('input[name="session"]')];
  const update = () => {
    const selected = options.filter(input => input.checked);
    all.checked = selected.length === 0;
    text.textContent = selected.length
      ? 'Sessions · ' + selected.length + ' selected · ' + selected.map(input => input.closest('label').textContent.trim()).join(', ')
      : 'Sessions · All sessions';
  };
  all.addEventListener('change', () => { options.forEach(input => { input.checked = false; }); update(); });
  options.forEach(input => input.addEventListener('change', update));
  update();
  // Native popovers escape the table's scrolling region without expanding the filter row.
  // Without Popover support, details/checkboxes still work as a normal inline control.
  if (typeof panel.showPopover === 'function') {
    panel.setAttribute('popover', 'auto');
    const position = () => {
      if (!panel.matches(':popover-open')) return;
      const rect = summary.getBoundingClientRect();
      panel.style.left = Math.max(8, Math.min(rect.left, innerWidth - panel.offsetWidth - 8)) + 'px';
      panel.style.top = Math.max(8, Math.min(rect.bottom + 4, innerHeight - panel.offsetHeight - 8)) + 'px';
    };
    details.addEventListener('toggle', () => {
      if (!details.open) { if (panel.matches(':popover-open')) panel.hidePopover(); return; }
      panel.showPopover();
      position();
    });
    panel.addEventListener('toggle', event => { if (event.newState === 'closed') details.open = false; });
    const close = () => { details.open = false; };
    window.addEventListener('resize', position);
    details.closest('.staff-table-scroll')?.addEventListener('scroll', () => {
      const anchor = summary.getBoundingClientRect();
      const region = details.closest('.staff-table-scroll').getBoundingClientRect();
      if (anchor.right < region.left || anchor.left > region.right) close();
      else position();
    });
  }
}
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

/* Third-batch date/navigation enhancements; server-side save actions stay explicit. */
const filterForm = document.querySelector('#booking-filter-form');
if (filterForm) {
  for (const name of ['start', 'end']) {
    const input = document.querySelector('#id_' + name);
    input?.addEventListener('change', () => { if (input.validity.valid) filterForm.requestSubmit(); });
  }
  for (const details of document.querySelectorAll('.session-filter')) {
    let changed = false;
    details.addEventListener('change', () => { changed = true; });
    // Popover content is moved to the top layer, but remains a DOM descendant.
    details.addEventListener('toggle', () => {
      if (!details.open && changed) { changed = false; filterForm.requestSubmit(); }
    });
    document.addEventListener('click', event => {
      if (details.open && !details.contains(event.target)) details.open = false;
    });
  }
}
for (const form of document.querySelectorAll('[data-auto-date]')) {
  form.querySelector('[data-date-fallback]').hidden = true;
  form.querySelector('input[type=date]').addEventListener('change', event => {
    if (event.target.value && event.target.validity.valid) form.requestSubmit();
  });
}
for (const date of document.querySelectorAll('[data-session-date]')) {
  const form = date.closest('form');
  const select = form.querySelector('[data-dated-sessions]');
  form.querySelector('[data-session-fallback]').hidden = true;
  let controller;
  date.addEventListener('change', async () => {
    if (controller) controller.abort();
    select.replaceChildren(new Option('Loading sessions…', ''));
    if (!date.value || !date.validity.valid) { select.replaceChildren(new Option('Choose a date first', '')); return; }
    controller = new AbortController();
    try {
      const params = new URLSearchParams({day: date.value});
      if (form.dataset.bookingId) params.set('booking', form.dataset.bookingId);
      const response = await fetch('/staff/bookings/sessions/?' + params, {signal: controller.signal, headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('Sessions could not be loaded. Reload and try again.');
      const data = await response.json();
      select.replaceChildren(new Option(data.sessions.length ? 'Choose a session' : 'No available sessions for this date', ''));
      for (const session of data.sessions) select.add(new Option(session.label, session.id));
      select.dispatchEvent(new Event('change', {bubbles: true}));
    } catch (error) {
      if (error.name !== 'AbortError') select.replaceChildren(new Option(error.message, ''));
    }
  });
}
for (const form of document.querySelectorAll('[data-public-estimate]')) {
  const content = form.querySelector('[data-public-estimate-content]');
  const status = form.querySelector('[data-public-estimate-status]');
  let timer, controller;
  const refresh = async () => {
    if (controller) controller.abort();
    controller = new AbortController();
    status.textContent = 'Updating estimate…';
    try {
      const response = await fetch(form.dataset.publicEstimate, {method: 'POST', body: new FormData(form), signal: controller.signal, headers: {Accept: 'application/json'}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Reload the page to update the estimate.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Check your group details.');
      content.innerHTML = data.html;
      status.textContent = 'Estimate only. Not saved yet.';
    } catch (error) {
      if (error.name !== 'AbortError') { content.replaceChildren(); status.textContent = error.message; }
    }
  };
  const queue = () => { clearTimeout(timer); timer = setTimeout(refresh, 180); };
  form.addEventListener('input', queue); form.addEventListener('change', queue);
  refresh();
}
