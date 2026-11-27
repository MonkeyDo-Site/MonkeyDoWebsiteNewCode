(() => {
  const form = document.querySelector('[data-membership-purchase]');
  if (!form) return;
  const field = name => form.elements.namedItem(name);
  const button = form.querySelector('[data-membership-confirm]');
  const error = form.querySelector('[data-membership-error]');
  const offer = form.querySelector('[data-membership-offer]');
  let sequence = 0, timer;
  const checked = name => !!field(name)?.checked;
  function visibility() {
    const comped = checked('comped');
    const needsCard = !comped && (field('billing').value === 'monthly' || field('expected_method').value === 'card');
    form.querySelector('[data-membership-card]').hidden = !needsCard;
    form.querySelector('[data-membership-receipt]').hidden = comped || field('expected_method').value === 'card';
    form.querySelector('[data-no-card-needed]').hidden = needsCard;
    const email = form.querySelector('[data-comped-email]');
    if (email) email.hidden = !comped;
    form.querySelector('[data-card-description]').textContent = field('billing').value === 'monthly' ? 'Monthly billing uses this card for the scheduled installments.' : 'This card will be charged for the full selected term.';
    if (!needsCard) field('method').value = '';
    button.disabled = !field('reviewed').value || !checked('accepted') || (needsCard && !field('method').value) || (!comped && field('expected_method').value !== 'card' && !checked('verified_received')) || (comped && !field('send_confirmation')?.value);
    const noun = field('operation')?.value === 'renewal' ? 'renewal' : field('operation')?.value === 'addition' ? 'additional places' : 'membership';
    button.textContent = comped ? `Confirm complimentary ${noun}` : field('expected_method').value === 'card' ? `Confirm ${noun} and charge card` : `Confirm ${noun} and record payment`;
  }
  async function preview() {
    const current = ++sequence;
    visibility();
    if (!field('customer').value) return;
    try {
      const response = await fetch(form.dataset.previewUrl, {method: 'POST', body: new FormData(form), credentials: 'same-origin', headers: {'X-CSRFToken': field('csrfmiddlewaretoken').value}});
      const result = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Please review the membership details.');
      if (field('reviewed').value && field('reviewed').value !== result.fingerprint) field('accepted').checked = false;
      offer.innerHTML = result.html;
      form.querySelector('[data-membership-terms]').textContent = result.terms;
      field('reviewed').value = result.fingerprint;
      if (result.starts_on) field('starts_on').value = result.starts_on;
      if (result.minimum_months) field('months').min = checked('minimum_override') || checked('comped') ? 1 : result.minimum_months;
      const selected = field('method').value;
      field('method').replaceChildren(new Option('Choose a saved card', ''), ...result.cards.map(card => new Option(card.label, card.id)));
      if (result.cards.some(card => card.id === selected)) field('method').value = selected;
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
  function change(event) {
    if (['accepted', 'method', 'verified_received', 'send_confirmation'].includes(event.target.name)) {visibility(); return;}
    if (!event.target.name || event.target.type === 'search') return;
    field('reviewed').value = '';
    field('accepted').checked = false;
    ++sequence;
    visibility();
    clearTimeout(timer);
    timer = setTimeout(preview, 250);
  }
  form.addEventListener('submit', event => {
    if (button.disabled) {event.preventDefault(); return;}
    // The request key stays stable across reloads; the server prevents duplicate collection.
    button.setAttribute('aria-busy', 'true');
  });
  preview();
})();
