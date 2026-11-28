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
  const selectionHash = () => JSON.stringify(['operation', 'prior_id', 'customer', 'kind', 'places', 'months', 'billing', 'starts_on', 'expected_method', 'minimum_override', 'comped', 'credit_amount', 'paid_visit_id', 'first_cash', 'first_check', 'first_zelle', 'first_gift_card', 'first_zelle_sender', 'first_zelle_received_on'].map(name => field(name)?.type === 'checkbox' ? checked(name) : field(name)?.value));
  function visibility() {
    const comped = checked('comped');
    const paidVisit = !!field('paid_visit_id')?.value;
    const due = form.dataset.paymentDue === undefined ? null : Number(form.dataset.paymentDue);
    const paymentRequired = due === null || due > 0;
    const split = !comped && field('expected_method').value === 'split';
    const value = kind => Number(field('first_'+kind)?.value || 0);
    const cashReceipt = split && value('cash') + value('check') > 0;
    const giftReceipt = split && value('gift_card') > 0;
    const bankReceipt = split && value('zelle') > 0;
    const splitBox=form.querySelector('[data-membership-first-split]');
    splitBox.hidden=!split;
    for(const input of splitBox.querySelectorAll('input'))input.disabled=!split;
    for(const [selector,show] of [['[data-first-gift]',giftReceipt],['[data-first-zelle]',bankReceipt]]){
      const box=form.querySelector(selector);box.hidden=!show;
      for(const input of box.querySelectorAll('input'))input.disabled=!show;
    }
    const needsCard = !comped && (form.dataset.needsCard === undefined ? (field('billing').value === 'monthly' || (['card','split'].includes(field('expected_method').value) && paymentRequired)) : form.dataset.needsCard === '1');
    const creditPanel = form.querySelector('[data-initial-credit]');
    if (creditPanel) creditPanel.hidden = paidVisit || comped || (creditAvailable <= 0 && !(Number(field('credit_amount')?.value) > 0));
    const useCredit = form.querySelector('[data-use-initial-credit]');
    if (useCredit) useCredit.disabled = paidVisit || !field('reviewed').value || creditAvailable <= 0;
    form.querySelector('[data-membership-card]').hidden = !needsCard;
    const cardControls = form.querySelector('[data-membership-card-controls]');
    if (cardControls) cardControls.hidden = !needsCard;
    form.querySelector('[data-membership-receipt]').hidden = comped || !paymentRequired || (split ? !cashReceipt : field('expected_method').value === 'card');
    const receiptText=form.querySelector('[data-membership-receipt] label span');
    receiptText.textContent=split?'I confirm the entered cash/check amounts were actually received.':'I confirm this membership payment was received';
    form.querySelector('[data-no-card-needed]').hidden = needsCard;
    const email = form.querySelector('[data-comped-email]');
    if (email) email.hidden = !comped;
    form.querySelector('[data-card-description]').textContent = field('billing').value === 'monthly' ? 'Monthly billing uses this card for the scheduled installments.' : 'This card will be charged for the remaining payment shown.';
    if (!needsCard) field('method').value = '';
    button.disabled = (needsCard && (form.dataset.membershipCardUnavailable === '1' || form.querySelector('[data-membership-card-entry]')?.dataset.blocked === '1')) || !field('reviewed').value || !checked('accepted') || (needsCard && !field('method').value) || (!comped && paymentRequired && (split ? ((cashReceipt&&!checked('verified_received'))||(giftReceipt&&!checked('first_gift_verified'))||(bankReceipt&&!checked('first_zelle_verified'))) : field('expected_method').value !== 'card'&&!checked('verified_received'))) || (comped && !field('send_confirmation')?.value);
    const noun = field('operation')?.value === 'renewal' ? 'renewal' : field('operation')?.value === 'addition' ? 'additional places' : 'membership';
    button.textContent = comped ? `Confirm complimentary ${noun}` : !paymentRequired ? `Confirm ${noun} and apply credit` : split ? `Confirm ${noun} — ${Number(form.dataset.splitManualTotal)>0?`record $${Number(form.dataset.splitManualTotal).toFixed(2)}`:''}${Number(form.dataset.splitManualTotal)>0&&Number(form.dataset.splitCardTotal)>0?' and ':''}${Number(form.dataset.splitCardTotal)>0?`charge card $${Number(form.dataset.splitCardTotal).toFixed(2)}`:''}` : field('expected_method').value === 'card' ? `Confirm ${noun} and charge card` : `Confirm ${noun} and record payment`;
    if (paidVisit) button.textContent = paymentRequired ? 'Apply visit and confirm membership — record $' + Number(due || 0).toFixed(2) : 'Apply visit and confirm membership';
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
      if (field('reviewed').value && field('reviewed').value !== result.fingerprint) {
        field('accepted').checked = false;
        for (const name of ['verified_received', 'first_gift_verified', 'first_zelle_verified']) if (field(name)) field(name).checked = false;
      }
      offer.innerHTML = result.html;
      if (result.payment_due_today !== undefined) form.dataset.paymentDue = result.payment_due_today;
      if (result.needs_card !== undefined) form.dataset.needsCard = result.needs_card ? '1' : '0';
      form.dataset.splitCardTotal=result.split_card_total||'0.00';form.dataset.splitManualTotal=result.split_manual_total||'0.00';
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
    if (['accepted', 'method', 'verified_received', 'first_gift_verified', 'first_zelle_verified', 'send_confirmation', 'member_retain'].includes(event.target.name)) {visibility(); return;}
    if (!event.target.name || event.target.type === 'search') return;
    const next = selectionHash();
    if (next === selection) {visibility(); return;}
    selection = next;
    delete form.dataset.paymentDue;delete form.dataset.needsCard;
    for(const name of ['verified_received','first_gift_verified','first_zelle_verified'])if(field(name))field(name).checked=false;
    field('reviewed').value = '';
    field('accepted').checked = false;
    ++sequence;
    visibility();
    clearTimeout(timer);
    timer = setTimeout(preview, 250);
  }
  form.querySelector('[data-use-initial-credit]')?.addEventListener('click', () => {
    field('credit_amount').value = Math.min(creditAvailable, Math.max(0,initialNet-(field('expected_method').value==='split'?['cash','check','zelle','gift_card'].reduce((sum,kind)=>sum+Number(field('first_'+kind)?.value||0),0):0))).toFixed(2);
    field('credit_amount').dispatchEvent(new Event('input', {bubbles:true}));
  });
  form.addEventListener('submit', event => {
    if (button.disabled) {event.preventDefault(); return;}
    // The request key stays stable across reloads; the server prevents duplicate collection.
    button.setAttribute('aria-busy', 'true');
  });
  preview();
})();
