/* Counts reserve places for 30 minutes. The final action confirms the booking. */
document.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('[data-staff-create]');
  if (!main) return;
  const card = document.querySelector('[data-card-setup]');
  const cardForm = card?.querySelector('[data-card-form]');
  const button = document.querySelector('[data-confirm-booking]');
  const status = main.querySelector('[data-create-status]');
  const estimate = main.querySelector('[data-create-estimate]');
  const waivers = main.querySelector('[data-create-waivers]');
  const payment = document.querySelector('[data-create-payment]');
  const paper = main.querySelector('[data-create-paper]');
  const paperFields = main.querySelector('[data-create-paper-fields]');
  const priceFields = main.querySelector('[data-owner-price-fields]');
  const signButton = main.querySelector('[data-create-sign]');
  const dialog = document.querySelector('[data-create-sign-dialog]');
  const signContent = dialog.querySelector('[data-create-sign-content]');
  const signStatus = dialog.querySelector('[data-create-sign-status]');
  let timer, queue = Promise.resolve(), busy = false, revision = '', customer = main.dataset.customer;
  let methodRevision = '', paused = false, hold = null, deadline = 0;
  const page = new URL(window.location.href);
  page.searchParams.set('draft', main.dataset.draft);
  window.history.replaceState(null, '', page);
  const endpoint = page.pathname + page.search;
  const errors = answer => answer.error || Object.values(answer.errors || {}).flatMap(group => Object.values(group).flatMap(items => items.map(item => item.message))).join(' ');
  const announce = message => { status.textContent = message; status.setAttribute('role', message ? 'alert' : 'status'); };
  const freeze = active => { busy = active; main.inert = active; payment.inert = active; button.disabled = active; };
  card?.addEventListener('staff-create-busy', event => freeze(event.detail));
  const controls = () => {
    paperFields.disabled = !paper.checked;
    const instructions = main.querySelector('[data-create-waiver-instructions]');
    if (instructions) instructions.hidden = main.querySelector('[name=waiver_choice]:checked')?.value !== 'link';
    const mode = main.querySelector('[name=price_mode]:checked')?.value || 'standard';
    const custom = main.querySelector('[data-custom-price]');
    if (custom) { custom.hidden = mode !== 'special'; main.elements.custom_admissions.disabled = mode !== 'special'; }
    const zelle = main.elements.expected_method.value === 'zelle';
    const sender = main.elements.zelle_sender;
    if (sender) { document.querySelector('[data-create-zelle]').hidden = !zelle; sender.disabled = !zelle; sender.required = zelle; }
  };
  const holdText = main.querySelector('[data-create-hold]');
  const renew = main.querySelector('[data-create-renew]');
  const showHold = () => {
    if (!hold?.expires_at) return;
    const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    renew.hidden = hold.active && left > 0;
    holdText.textContent = hold.active && left > 0
      ? `Places reserved: ${hold.children} children · ${hold.adults} adults · ${hold.babies} babies. Time remaining: ${Math.floor(left / 60)}:${String(left % 60).padStart(2,'0')}. Confirm booking to keep these places.`
      : 'The 30-minute reservation expired and these places were released. Reserve them again before confirming.';
  };
  const apply = answer => {
    if (answer.membership_html !== undefined) main.querySelector('[data-create-memberships]').innerHTML = answer.membership_html;
    if (answer.hold) { hold = answer.hold; deadline = Date.now() + (hold.seconds_remaining || 0) * 1000; showHold(); }
    if (answer.html !== undefined || !answer.valid) estimate.innerHTML = answer.html || '<p>Complete the visit details to see the price.</p>';
    if (answer.capacity) main.querySelector('.session-capacity-info').textContent = answer.capacity;
    if (answer.waivers_html && answer.waiver_revision !== revision) {
      waivers.innerHTML = answer.waivers_html;
      revision = answer.waiver_revision;
    }
    signButton.disabled = !answer.valid;
    if (answer.methods && cardForm) {
      const identityChanged = customer !== String(answer.customer_id || '');
      const next = JSON.stringify(answer.methods);
      if (identityChanged || methodRevision !== next) {
        const selected = identityChanged ? 'new' : cardForm.elements.method.value;
        const fieldset = cardForm.querySelector('[data-card-methods]');
        fieldset.replaceChildren();
        const legend = document.createElement('legend'); legend.textContent = 'Choose a card'; fieldset.append(legend);
        for (const method of [...answer.methods, {id:'new', last_four:''}]) {
          const label = document.createElement('label'), input = document.createElement('input');
          input.type = 'radio'; input.name = 'method'; input.value = method.id;
          input.checked = method.id === selected || (answer.ready && method.id === answer.selected_method && card.dataset.choiceDirty !== '1');
          label.append(input, method.id === 'new' ? ' Enter a new card' : ` Saved payment method ending in ${method.last_four}`);
          fieldset.append(label);
        }
        if (!cardForm.elements.method.value) cardForm.querySelector('[name=method][value=new]').checked = true;
        methodRevision = next;
      }
      if (identityChanged) {
        main.elements.payment_consent.value = '';
        for (const choice of cardForm.querySelectorAll('[name=retain], [name=agree_payment]')) choice.checked = false;
        cardForm.elements.request_key.value = answer.request_key;
        paper.checked = false; paperFields.disabled = true;
        for (const field of paperFields.querySelectorAll('input,textarea,select')) field.value = '';
      }
      customer = String(answer.customer_id || '');
      card.querySelector('[data-card-cancellation]').textContent = answer.cancellation;
      card.dispatchEvent(new CustomEvent('staff-create-context', {detail:{...answer, identity_changed:identityChanged}}));
    }
    const comped = answer.valid && answer.comped;
    payment.hidden = comped;
    document.querySelector('[data-create-comped]').hidden = !comped;
    announce(answer.valid ? '' : errors(answer));
    controls();
  };
  const send = async (intent, data = new FormData(main)) => {
    data.set('intent', intent);
    const response = await fetch(endpoint, {method:'POST', body:data, headers:{Accept:'application/json'}, cache:'no-store'});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The page could not confirm a response. Reload this draft before trying again.');
    const answer = await response.json();
    if (answer.confirmed) { window.location.assign(answer.url); return answer; }
    apply(answer);
    return answer;
  };
  const preview = () => {
    if (busy || paused) return queue;
    const data = new FormData(main);
    queue = queue.then(() => send('preview', data)).catch(error => { announce(error.message); return null; });
    return queue;
  };
  const changed = event => {
    if (event.target.form !== main || event.target.type === 'search') return;
    controls(); clearTimeout(timer);
    timer = window.setTimeout(preview, 220);
  };
  document.addEventListener('input', changed);
  document.addEventListener('change', changed);
  main.querySelector('[data-owner-price-toggle]')?.addEventListener('click', event => {
    priceFields.hidden = !priceFields.hidden;
    event.currentTarget.setAttribute('aria-expanded', String(!priceFields.hidden));
  });
  const prepare = async () => {
    clearTimeout(timer);
    if (!main.reportValidity()) return null;
    paused = true; freeze(true);
    try {
      await queue;
      const answer = await send('prepare');
      if (!answer.valid) { freeze(false); paused = false; status.scrollIntoView({block:'center'}); return null; }
      main.elements.reviewed_hash.value = answer.reviewed_hash;
      // The card handler takes over immediately; no further preview writes may race it.
      return answer;
    } catch (error) { freeze(false); paused = false; throw error; }
  };
  renew.addEventListener('click', async () => {
    clearTimeout(timer); paused = true; freeze(true);
    try { await queue; await send('renew'); }
    catch (error) { announce(error.message); }
    finally { freeze(false); paused = false; }
  });
  window.setInterval(showHold,1000);
  // Read-only refresh: an open tab never renews or extends the reservation.
  window.setInterval(async () => {
    if (busy || paused || !hold?.expires_at) return;
    const statusURL = new URL(endpoint,window.location.origin); statusURL.searchParams.set('hold_status','1');
    try {
      const response = await fetch(statusURL,{headers:{Accept:'application/json'},cache:'no-store'});
      if (!response.ok) return;
      const answer = await response.json();
      hold = answer.hold; deadline = Date.now() + (hold.seconds_remaining || 0) * 1000; showHold();
      if (answer.capacity) main.querySelector('.session-capacity-info').textContent = answer.capacity;
    } catch { /* The server still releases expired holds when capacity is read. */ }
  },15000);
  if (cardForm) card.staffCreatePrepare = prepare;
  card?.addEventListener('staff-create-busy', event => { if (!event.detail) paused = false; });
  main.addEventListener('submit', async event => {
    // payment-setup first prepares and saves/selects a card, then submits once ready.
    if (event.defaultPrevented) return;
    event.preventDefault();
    if (!cardForm) {
      const answer = await prepare();
      if (!answer) return;
      if (!answer.comped) { freeze(false); paused = false; announce('Secure card setup is unavailable. This booking has not been confirmed.'); return; }
    }
    freeze(true); paused = true;
    try {
      const answer = await send('confirm');
      if (answer.confirmed) return;
    } catch (error) { announce(error.message); }
    card?.dispatchEvent(new CustomEvent('staff-create-final-error'));
    freeze(false); paused = false;
    status.scrollIntoView({block:'center'});
  });
  const bindSignature = () => {
    const signForm = signContent.querySelector('form');
    const relation = signForm.querySelector('[name=relationship]');
    const names = signForm.querySelector('[name=minors]');
    relation.addEventListener('change', () => {
      const key = relation.value === 'Parent' ? 'parent' : relation.value === 'Legal guardian' ? 'guardian' : 'default';
      signForm.querySelector(`label[for="${names.id}"]`).textContent = names.dataset[key + 'Label'];
      const help = names.parentElement.querySelector('.field-help');
      if (help) help.textContent = names.dataset[key + 'Help'];
    });
    signForm.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = signForm.querySelector('button[type=submit]'); submit.disabled = true;
      try {
        const response = await fetch(main.dataset.signUrl, {method:'POST', body:new FormData(signForm), headers:{Accept:'application/json'}});
        const answer = await response.json();
        if (answer.signed) {
          dialog.close(); paused = false; freeze(false);
          await preview();
          return;
        }
        if (answer.html) { signContent.innerHTML = answer.html; bindSignature(); }
        signStatus.textContent = answer.error || 'Review the waiver details above.';
      } catch { signStatus.textContent = 'The signature response could not be confirmed. Keep this window open and try again using the same signature request.'; submit.disabled = false; }
    });
  };
  signButton.addEventListener('click', async () => {
    clearTimeout(timer); paused = true; freeze(true);
    try {
      await queue;
      const answer = await send('preview');
      if (!answer.valid) throw new Error('Complete the customer and visit details before signing.');
      const response = await fetch(main.dataset.signUrl, {headers:{Accept:'application/json'}, cache:'no-store'});
      const content = await response.json();
      if (!response.ok) throw new Error(content.error || 'Waiver signing is unavailable.');
      signContent.innerHTML = content.html; signStatus.textContent = ''; bindSignature(); dialog.showModal();
    } catch (error) { announce(error.message); freeze(false); paused = false; }
  });
  dialog.querySelector('[data-create-sign-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { freeze(false); paused = false; });
  controls();
  if (main.elements.customer.value && main.elements.session.value) preview();
});
