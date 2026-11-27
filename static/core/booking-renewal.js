document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('membership-renewal-actions');
  if (!form) return;
  const main = document.querySelector('[data-staff-create]');
  const sent = new Set();
  const identityMatches = row => !main || String(main.elements.customer.value) === row.dataset.customer;
  const post = async value => {
    const data = new FormData(form); data.set('decision', value);
    const response = await fetch(form.action, {method:'POST', body:data, headers:{Accept:'application/json'}, credentials:'same-origin'});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Return to your booking and sign in again if needed.');
    const answer = await response.json();
    if (!response.ok) throw new Error(answer.error || 'Refresh the booking renewal choices.');
    return answer;
  };
  const seen = async row => {
    const key = `${row.dataset.flow}:${row.dataset.purchase}:${row.dataset.window}`;
    if (sent.has(key) || !identityMatches(row)) return;
    sent.add(key);
    try { await post(row.dataset.token + '.seen'); }
    catch { sent.delete(key); } // Explicit choices still record that their prompt was shown.
  };
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      observer.unobserve(entry.target); seen(entry.target);
    }
  }) : null;
  const scan = () => {
    for (const row of document.querySelectorAll('[data-renewal-row]')) {
      if (row.dataset.observed) continue;
      row.dataset.observed = '1';
      if (observer) observer.observe(row); else seen(row);
    }
  };
  new MutationObserver(scan).observe(document.body, {childList:true, subtree:true});
  scan();
  form.addEventListener('submit', async event => {
    const button = event.submitter, row = button?.closest('[data-renewal-row]');
    if (!row) return;
    event.preventDefault();
    const feedback = row.querySelector('[data-renewal-feedback]');
    const value = button.value;
    const renewing = value.endsWith('.renew');
    const child = renewing ? window.open('about:blank', '_blank') : null;
    if (child) child.opener = null;
    const buttons = [...row.querySelectorAll('button')];
    const previous = buttons.map(item => item.disabled);
    buttons.forEach(item => { item.disabled = true; });
    feedback.textContent = 'Saving your choice…';
    try {
      if (!identityMatches(row)) throw new Error('The customer changed. Review their current renewal choices.');
      if (main?.staffCreateFlush) {
        const answer = await main.staffCreateFlush();
        if (!answer || String(answer.customer_id || '') !== row.dataset.customer || !identityMatches(row)) throw new Error('The customer changed. Review their current renewal choices.');
      }
      const answer = await post(value);
      if (!identityMatches(row)) throw new Error('The customer changed. Return to the booking for their current details.');
      const current = [...document.querySelectorAll('[data-renewal-row]')].find(item => item.dataset.purchase === row.dataset.purchase && item.dataset.flow === row.dataset.flow) || row;
      const status = current.querySelector('[data-renewal-feedback]');
      current.querySelector('[data-renewal-buttons]').hidden = true;
      status.textContent = answer.message || 'Continue renewal in the other tab, then return here to finish booking.';
      if (answer.url) {
        const url = new URL(answer.url, window.location.origin);
        if (url.origin !== window.location.origin) throw new Error('Return to the current booking to open renewal.');
        if (child && !child.closed) child.location.assign(url.href);
        else {
          const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener';
          link.textContent = 'Continue to renewal'; status.append(' ', link);
        }
      } else if (child) child.close();
    } catch (error) {
      if (child) child.close();
      feedback.textContent = error.message;
      buttons.forEach((item,index) => { item.disabled = previous[index]; });
    }
  });
  window.addEventListener('focus', () => {
    if (main?.staffCreateFlush) main.staffCreateFlush().catch(() => {});
    else document.querySelector('[data-public-estimate]')?.membershipRefresh?.();
  });
});
