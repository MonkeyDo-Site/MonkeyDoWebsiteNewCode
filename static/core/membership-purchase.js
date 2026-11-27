(() => {
  const form = document.querySelector('[data-membership-purchase]');
  if (!form) return;
  const field = name => form.elements.namedItem(name);
  const button = form.querySelector('[data-membership-confirm]');
  const error = form.querySelector('[data-membership-error]');
  const offer = form.querySelector('[data-membership-offer]');
  let sequence = 0, timer;
  let selection, creditAvailable = 0, initialNet = 0;
  let creditCustomer = field('customer').value;
  const checked = name => !!field(name)?.checked;
  const selectionHash = () => JSON.stringify(['operation', 'prior_id', 'customer', 'kind', 'places', 'months', 'billing', 'starts_on', 'expected_method', 'minimum_override', 'comped', 'credit_amount'].map(name => field(name)?.type === 'checkbox' ? checked(name) : field(name)?.value));
  function visibility() {
    const comped = checked('comped');
    const due = form.dataset.paymentDue === undefined ? null : Number(form.dataset.paymentDue);
    const paymentRequired = due === null || due > 0;
    const needsCard = !comped && (field('billing').value === 'monthly' || (field('expected_method').value === 'card' && paymentRequired));
    const creditPanel = form.querySelector('[data-initial-credit]');
    if (creditPanel) creditPanel.hidden = comped || (creditAvailable <= 0 && !(Number(field('credit_amount')?.value) > 0));
    const useCredit = form.querySelector('[data-use-initial-credit]');
    if (useCredit) useCredit.disabled = !field('reviewed').value || creditAvailable <= 0;
    form.querySelector('[data-membership-card]').hidden = !needsCard;
    const cardControls = form.querySelector('[data-membership-card-controls]');
    if (cardControls) cardControls.hidden = !needsCard;
    form.querySelector('[data-membership-receipt]').hidden = comped || !paymentRequired || field('expected_method').value === 'card';
    form.querySelector('[data-no-card-needed]').hidden = needsCard;
    const email = form.querySelector('[data-comped-email]');
    if (email) email.hidden = !comped;
    form.querySelector('[data-card-description]').textContent = field('billing').value === 'monthly' ? 'Monthly billing uses this card for the scheduled installments.' : 'This card will be charged for the remaining payment shown.';
    if (!needsCard) field('method').value = '';
    button.disabled = (needsCard && (form.dataset.membershipCardUnavailable === '1' || form.querySelector('[data-membership-card-entry]')?.dataset.blocked === '1')) || !field('reviewed').value || !checked('accepted') || (needsCard && !field('method').value) || (!comped && paymentRequired && field('expected_method').value !== 'card' && !checked('verified_received')) || (comped && !field('send_confirmation')?.value);
    const noun = field('operation')?.value === 'renewal' ? 'renewal' : field('operation')?.value === 'addition' ? 'additional places' : 'membership';
    button.textContent = comped ? `Confirm complimentary ${noun}` : !paymentRequired ? `Confirm ${noun} and apply credit` : field('expected_method').value === 'card' ? `Confirm ${noun} and charge card` : `Confirm ${noun} and record payment`;
  }
  async function preview() {
    const current = ++sequence;
    selection = selectionHash();
    visibility();
    if (!field('customer').value) return;
    try {
      const response = await fetch(form.dataset.previewUrl, {method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: {'X-CSRFToken': field('csrfmiddlewaretoken').value}});
      const result = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Please review the membership details.');
      if (field('reviewed').value && field('reviewed').value !== result.fingerprint) field('accepted').checked = false;
      offer.innerHTML = result.html;
      if (result.payment_due_today !== undefined) form.dataset.paymentDue = result.payment_due_today;
      if (result.credit_available !== undefined) {
        creditAvailable = Number(result.credit_available); initialNet = Number(result.initial_net);
        const balance = form.querySelector('[data-credit-available]');
        if (balance) balance.textContent = creditAvailable.toFixed(2);
      }
      form.querySelector('[data-membership-terms]').textContent = result.terms;
      field('reviewed').value = result.fingerprint;
      if (result.starts_on) field('starts_on').value = result.starts_on;
      if (result.minimum_months) field('months').min = checked('minimum_override') || checked('comped') ? 1 : result.minimum_months;
      selection = selectionHash();
      const selected = field('method').value;
      const allowNew = Array.from(field('method').options).some(option => option.value === 'new');
      field('method').replaceChildren(new Option('Choose a saved card', ''), ...result.cards.map(card => new Option(card.label, card.id)), ...(allowNew ? [new Option('Enter a new card', 'new')] : []));
      if (result.cards.some(card => card.id === selected) || (allowNew && selected === 'new')) field('method').value = selected;
      error.hidden = true;
    } catch (failure) {
      if (current !== sequence) return;
      field('reviewed').value = '';
      error.textContent = failure.message || 'The current price could not be loaded. Please try again.';
      error.hidden = false;
    }
    visibility();
  }
  form.addEventListener('input', change);
  form.addEventListener('change', change);
  form.addEventListener('membership-card-state', visibility);
  function change(event) {
    if (field('credit_amount') && ((event.target.name === 'customer' && creditCustomer !== field('customer').value) || (event.target.name === 'comped' && checked('comped')))) {
      field('credit_amount').value = '0.00'; creditCustomer = field('customer').value;
    }
    if (['accepted', 'method', 'verified_received', 'send_confirmation', 'member_retain'].includes(event.target.name)) {visibility(); return;}
    if (!event.target.name || event.target.type === 'search') return;
    const next = selectionHash();
    if (next === selection) {visibility(); return;}
    selection = next;
    delete form.dataset.paymentDue;
    field('reviewed').value = '';
    field('accepted').checked = false;
    ++sequence;
    visibility();
    clearTimeout(timer);
    timer = setTimeout(preview, 250);
  }
  form.querySelector('[data-use-initial-credit]')?.addEventListener('click', () => {
    field('credit_amount').value = Math.min(creditAvailable, initialNet).toFixed(2);
    field('credit_amount').dispatchEvent(new Event('input', {bubbles:true}));
  });
  form.addEventListener('submit', event => {
    if (button.disabled) {event.preventDefault(); return;}
    // The request key stays stable across reloads; the server prevents duplicate collection.
    button.setAttribute('aria-busy', 'true');
  });
  preview();
})();
