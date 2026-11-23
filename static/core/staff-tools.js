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
  let sessionRequest, filterTimer;
  const filterStatus = document.createElement('p');
  filterStatus.className = 'caption'; filterStatus.setAttribute('role', 'status');
  filterForm.after(filterStatus);
  for (const details of document.querySelectorAll('.session-filter')) {
    details.addEventListener('change', () => {
      clearTimeout(filterTimer);
      if (sessionRequest) sessionRequest.abort();
      filterTimer = setTimeout(async () => {
        sessionRequest = new AbortController();
        const url = new URL(location.href);
        url.search = new URLSearchParams(new FormData(filterForm)).toString();
        filterStatus.textContent = 'Updating bookings…';
        try {
          const response = await fetch(url, {signal: sessionRequest.signal, headers: {Accept: 'text/html'}});
          if (!response.ok) throw new Error('Could not filter bookings. Use Apply filters to try again.');
          const next = new DOMParser().parseFromString(await response.text(), 'text/html');
          if (!next.querySelector('.booking-table')) { location.assign(url); return; }
          const returnedFilters = next.querySelector('#booking-filter-form');
          if (returnedFilters) filterForm.replaceChildren(...returnedFilters.childNodes);
          for (const selector of ['.booking-table tbody', '.booking-table tfoot', '.booking-table thead tr:last-child', '[data-session-overview]', '[data-staff-pagination]']) {
            const current = document.querySelector(selector), replacement = next.querySelector(selector);
            if (current && replacement) current.replaceWith(replacement);
          }
          bindPageSizes();
          history.replaceState(null, '', url);
          filterStatus.textContent = filterForm.querySelector('.errorlist') ? 'Review the highlighted booking filters.' : 'Bookings updated for the selected sessions.';
        } catch (error) {
          if (error.name !== 'AbortError') filterStatus.textContent = error.message;
        }
      }, 120);
    });
    document.addEventListener('click', event => {
      if (details.open && !details.contains(event.target)) details.open = false;
    });
  }
}
for (const form of document.querySelectorAll('[data-auto-date]')) {
  const fallback = form.querySelector('[data-date-fallback]');
  if (fallback) fallback.hidden = true;
  for (const date of form.querySelectorAll('input[type=date]')) {
    date.addEventListener('change', event => {
      if (event.target.validity.valid) form.requestSubmit();
    });
  }
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
      for (const session of data.sessions) {
        const option=new Option(session.label,session.id);option.dataset.capacity=session.capacity||'';select.add(option);
      }
      select.dispatchEvent(new Event('change', {bubbles: true}));
    } catch (error) {
      if (error.name !== 'AbortError') select.replaceChildren(new Option(error.message, ''));
    }
  });
}
/* Public-only supervised quantities; staff editors retain explicit validation. */
for (const form of document.querySelectorAll('[data-public-estimate]')) {
  const adults = form.querySelector('[name=adults]'), babies = form.querySelector('[name=babies]');
  let wasSupervised = false;
  let openAdults = adults.value || '1', openBabies = babies.value || '0';
  const selected = () => form.querySelector('[name=play_type]:checked')?.value === 'supervised';
  if (selected()) { openAdults = '1'; openBabies = '0'; }
  const popup = document.createElement('dialog');
  popup.className = 'supervised-message'; popup.setAttribute('aria-label', 'Supervised play is children only');
  popup.innerHTML = '<p>Supervised play is children only</p><button type="button" class="button small">OK</button>';
  form.after(popup);
  popup.querySelector('button').addEventListener('click', () => popup.close());
  const explain = event => {
    if (!selected()) return;
    if (event.type === 'keydown' && !['ArrowUp', 'ArrowDown', 'Backspace', 'Delete', '-', '+', '.', ...'0123456789'].includes(event.key)) return;
    event.preventDefault();
    if (typeof popup.showModal === 'function') { if (!popup.open) popup.showModal(); }
    else window.alert('Supervised play is children only');
  };
  for (const field of [adults, babies]) {
    field.addEventListener('pointerdown', explain);
    field.addEventListener('keydown', explain);
  }
  const sync = () => {
    const supervised = selected();
    if (supervised && !wasSupervised) { openAdults = adults.value; openBabies = babies.value; }
    for (const [field, oldValue] of [[adults, openAdults], [babies, openBabies]]) {
      field.readOnly = supervised;
      field.setAttribute('aria-readonly', String(supervised));
      field.max = supervised ? '0' : '50';
      if (supervised) field.value = '0';
      else if (wasSupervised) field.value = oldValue;
    }
    wasSupervised = supervised;
  };
  // For supervised-only sessions, switching is unavailable; quantities still start at zero.
  if (selected()) wasSupervised = true;
  sync();
  for (const radio of form.querySelectorAll('[name=play_type]')) radio.addEventListener('change', sync);
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

function bindPageSizes() {
  for (const select of document.querySelectorAll('[data-page-size]')) {
    if (select.dataset.bound) continue;
    select.dataset.bound = '1';
    select.form.querySelector('[data-page-size-fallback]').hidden = true;
    select.addEventListener('change', () => select.form.requestSubmit());
  }
}
bindPageSizes();
for (const form of document.querySelectorAll('[data-reviewed-checkout]')) {
  const final = form.querySelector('[data-confirm-checkout]');
  if (!final) continue;
  for (const input of form.querySelectorAll('input:not([type=hidden]), select, textarea')) {
    input.addEventListener('input', () => {
      final.disabled = true;
      form.querySelector('[data-review-changed]').hidden = false;
      form.elements.reviewed_hash.value = '';
    });
  }
}
for (const form of document.querySelectorAll('[data-reviewed-checkout]')) {
  const method = form.querySelector('[name=method]');
  if (!method) continue;
  const field = name => form.querySelector(`[data-field="${name}"]`);
  const visibility = (name, visible) => {
    const wrap = field(name);
    if (!wrap) return;
    wrap.hidden = !visible;
    for (const input of wrap.querySelectorAll('input,select')) input.disabled = !visible;
  };
  const sync = () => {
    const fee = form.querySelector('[name=charge_fee]');
    const closureHasFee = !fee || fee.value === 'yes';
    visibility('method', closureHasFee);
    for (const kind of ['cash','check','zelle','gift_card']) visibility(`${kind}_amount`, method.value === 'split');
    const zelleAmount = form.querySelector('[name=zelle_amount]');
    const giftAmount = form.querySelector('[name=gift_card_amount]');
    visibility('zelle_verified', closureHasFee && (method.value === 'zelle' || (method.value === 'split' && Number(zelleAmount?.value) > 0)));
    visibility('gift_card_verified', closureHasFee && (method.value === 'gift_card' || (method.value === 'split' && Number(giftAmount?.value) > 0)));
  };
  form.addEventListener('input', sync);
  form.addEventListener('change', sync);
  sync();
}

/* Zelle sender details are needed only for the selected Zelle payment path. */
for (const panel of document.querySelectorAll('[data-zelle-sender]')) {
  const form = panel.closest('form');
  const method = form?.elements.expected_method;
  if (!method) continue;
  const sync = () => { panel.hidden = method.value !== 'zelle'; };
  method.addEventListener('change', sync);
  sync();
}

/* Keep payment review focused on the actual tender; server validation is authoritative. */
for (const form of document.querySelectorAll('[data-reviewed-checkout]')) {
  const method = form.elements.method;
  if (!method) continue;
  const sync = () => {
    const kind = method.value;
    const split = kind === 'split';
    const show = (name, visible) => {
      const row = form.querySelector(`[data-field="${name}"]`);
      if (row && !row.querySelector('.errorlist')) row.hidden = !visible;
    };
    for (const tender of ['cash', 'check', 'zelle', 'gift_card']) show(`${tender}_amount`, split);
    show('received_on', !['card', 'comped'].includes(kind));
    show('zelle_sender', kind === 'zelle' || split);
    show('zelle_verified', kind === 'zelle' || split);
    show('gift_card_verified', kind === 'gift_card' || split);
  };
  method.addEventListener('change', sync);
  sync();
}

/* A group may reserve places and request the shared link before all parents sign. */
for (const form of document.querySelectorAll('.waiver-coverage')) {
  const shared = form.elements.share_requested;
  if (!shared) continue;
  const sync = () => {
    for (const name of ['additional_minors', 'coverage_confirmed']) {
      const row = form.querySelector(`[data-field="${name}"]`);
      if (!row) continue;
      row.hidden = shared.checked;
      for (const input of row.querySelectorAll('input')) {
        input.disabled = shared.checked;
        if (name !== 'signatures') input.required = !shared.checked;
      }
    }
  };
  shared.addEventListener('change', sync);
  sync();
}

for (const notice of document.querySelectorAll('[data-special-price-notice]')) {
  const form = notice.closest('form');
  if (!form) continue;
  const changed = () => {
    const counts = ['children', 'adults', 'babies'].some(name => form.elements[name] && form.elements[name].value !== notice.dataset[`original${name[0].toUpperCase()+name.slice(1)}`]);
    const mode = form.elements.supervised;
    notice.hidden = !counts && (!mode || String(Number(mode.checked)) === notice.dataset.originalSupervised);
  };
  form.addEventListener('input', changed);
  form.addEventListener('change', changed);
  changed();
}

for(const select of document.querySelectorAll('[data-dated-sessions]')){
 const box=document.createElement('p');box.className='caption session-capacity-info';box.setAttribute('role','status');select.after(box);
 select.addEventListener('change',()=>{box.textContent=select.selectedOptions[0]?.dataset.capacity||'';});
}
