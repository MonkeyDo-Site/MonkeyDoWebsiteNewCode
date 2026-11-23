for (const form of document.querySelectorAll('[data-arrival-live]')) {
  const button=form.querySelector('[data-arrival-confirm]'), status=form.querySelector('[data-arrival-status]');
  let timer,controller,generation=0;
  const sync=()=>{
    const method=form.elements.method.value;
    for(const field of form.querySelectorAll('[data-noncard-fields] [data-arrival-field]')) {
      const name=field.dataset.arrivalField;
      const allowed={cash_amount:method==='split',check_amount:method==='split',zelle_amount:method==='split',gift_card_amount:method==='split',zelle_verified:method==='zelle'||method==='split',gift_card_verified:method==='gift_card'||method==='split',received_on:method==='zelle'||method==='split',zelle_sender:method==='zelle'||method==='split'};
      field.hidden=!allowed[name];
      for(const input of field.querySelectorAll('input,select'))input.disabled=field.hidden;
    }
  };
  const update=async()=>{
    const serial=++generation;
    if(controller)controller.abort();controller=new AbortController();
    sync();button.disabled=true;status.textContent='Updating price and balance…';
    try{
      const response=await fetch(location.href,{method:'POST',body:new FormData(form),headers:{Accept:'application/json'},signal:controller.signal,cache:'no-store'});
      const data=await response.json();if(serial!==generation)return;
      if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the details above.');
      form.querySelector('[data-arrival-price]').innerHTML=data.html;
      form.elements.reviewed_hash.value=data.hash||'';button.textContent=data.label||'Confirm arrival';button.disabled=!data.can_confirm;
      status.textContent=data.can_confirm?'':'Confirm waiver coverage to finish arrival.';
    }catch(e){if(e.name!=='AbortError'&&serial===generation)status.textContent=e.message;}
  };
  form.addEventListener('input',()=>{button.disabled=true;clearTimeout(timer);timer=setTimeout(update,250);});
  form.addEventListener('change',()=>{sync();button.disabled=true;clearTimeout(timer);timer=setTimeout(update,80);});
  form.addEventListener('submit',e=>{if(button.disabled||!form.elements.reviewed_hash.value){e.preventDefault();update();}});
  window.addEventListener('focus',()=>update());sync();
}
for(const form of document.querySelectorAll('[data-paper-entry]')){
  const check=form.elements.paper_signed,fields=form.querySelector('.paper-entry');
  const sync=()=>{fields.hidden=!check.checked;for(const field of fields.querySelectorAll('input,select,textarea'))field.disabled=!check.checked;};
  check.addEventListener('change',sync);sync();
}
// Zelle sender is relevant only to the selected method, including method switching.
for(const form of document.querySelectorAll('form')){
  const method=form.elements.expected_method||form.elements.payment_method;
  const sender=form.querySelector('[data-field="zelle_sender"]');
  if(!method||!sender)continue;
  const sync=()=>{sender.hidden=method.value!=='zelle';for(const field of sender.querySelectorAll('input'))field.disabled=sender.hidden;};
  method.addEventListener('change',sync);sync();
}
