/* Read-only cancellation previews; only the explicit final button changes records. */
(() => {
  for(const refundForm of document.querySelectorAll('[data-membership-refund]')){
    const input=refundForm.elements.refund_amount,button=refundForm.querySelector('[data-refund-confirm]');
    let last=input.value;
    const display=()=>{
      const value=Number(input.value||refundForm.dataset.defaultAmount);
      const record=refundForm.elements.card_refund_action?.value==='record';
      for(const name of ['completed_provider_reference','completed_confirmed']){
        const field=refundForm.elements[name];if(!field)continue;
        field.disabled=!record;field.required=record;
        field.closest('.arrival-field').hidden=!record;
      }
      button.textContent=`${record?'Verify and record completed Banquest refund':refundForm.dataset.refundLabel} — $${Number.isFinite(value)?value.toFixed(2):refundForm.dataset.defaultAmount}`;
    };
    const changed=()=>{if(input.value!==last){for(const name of ['manual_returned','completed_confirmed'])if(refundForm.elements[name])refundForm.elements[name].checked=false;}last=input.value;display();};
    input.addEventListener('input',changed);input.addEventListener('change',changed);
    refundForm.elements.card_refund_action?.addEventListener('change',()=>{if(refundForm.elements.completed_confirmed)refundForm.elements.completed_confirmed.checked=false;display();});display();
  }
  const form=document.querySelector('[data-membership-cancel]');
  if(!form)return;
  const field=name=>form.elements.namedItem(name);
  const button=form.querySelector('[data-cancel-confirm]'),error=form.querySelector('[data-cancel-error]');
  let needsEarly=form.dataset.requiresEarly==='1',hasManual=form.dataset.hasManual==='1',refund=form.dataset.refundAmount||'0.00',generation=0,timer;
  const selection=()=>JSON.stringify([field('timing').value,field('refund_amount').value]);
  let lastSelection=selection();
  const display=()=>{
    const manual=hasManual&&field('refund_action').value==='process'&&Number(refund)>0;
    form.querySelector('[data-cancel-manual]').hidden=!manual;
    field('manual_refunds_confirmed').disabled=!manual;
    field('manual_refunds_confirmed').required=manual;
    form.querySelector('[data-cancel-early]').hidden=!needsEarly;
    field('early_override').disabled=!needsEarly;
    field('early_override').required=needsEarly;
    button.disabled=!field('reviewed').value||!field('reason').value.trim()||!field('send_confirmation').value||(needsEarly&&!field('early_override').checked)||(manual&&!field('manual_refunds_confirmed').checked);
    button.textContent=Number(refund)<=0?'Confirm membership cancellation':field('refund_action').value==='due'?`Cancel membership — $${refund} refund due`:hasManual?`Cancel membership and record/request $${refund} refund`:`Cancel membership and request $${refund} card refund`;
  };
  const preview=async()=>{
    const current=++generation,data=new FormData(form);data.set('action','cancel_preview');
    try{
      const response=await fetch(location.href,{method:'POST',body:data,headers:{Accept:'application/json','X-CSRFToken':field('csrfmiddlewaretoken').value},cache:'no-store'});
      const result=await response.json();if(current!==generation)return;
      if(!response.ok)throw new Error(result.error||'Review the cancellation details.');
      form.querySelector('[data-cancel-quote]').innerHTML=result.html;
      field('reviewed').value=result.fingerprint;needsEarly=result.requires_early_override;hasManual=result.has_manual;refund=result.refund_amount;error.hidden=true;
    }catch(failure){if(current!==generation)return;field('reviewed').value='';error.textContent=failure.message||'The cancellation review could not be loaded.';error.hidden=false;}
    display();
  };
  const changed=event=>{
    if(['timing','refund_amount'].includes(event.target.name)){
      const next=selection();if(next===lastSelection)return;lastSelection=next;
      ++generation;field('reviewed').value='';field('early_override').checked=false;field('manual_refunds_confirmed').checked=false;clearTimeout(timer);timer=setTimeout(preview,180);
    }else if(event.target.name==='refund_action')field('manual_refunds_confirmed').checked=false;
    display();
  };
  form.addEventListener('input',changed);form.addEventListener('change',changed);
  form.addEventListener('submit',event=>{if(button.disabled)event.preventDefault();else button.setAttribute('aria-busy','true');});
  display();
})();
