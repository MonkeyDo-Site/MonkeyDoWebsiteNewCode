for (const form of document.querySelectorAll('[data-arrival-live]')) {
  const button=form.querySelector('[data-arrival-confirm]'), status=form.querySelector('[data-arrival-status]');
  let timer,controller,generation=0;
  const sync=()=>{
    const method=form.elements.method.value;
    for(const field of form.querySelectorAll('[data-noncard-fields] [data-arrival-field]')) {
      const name=field.dataset.arrivalField;
      const allowed={cash_amount:method==='split',check_amount:method==='split',zelle_amount:method==='split',gift_card_amount:method==='split',zelle_verified:method==='split',gift_card_verified:method==='gift_card'||method==='split',received_on:method==='split',zelle_sender:method==='split'};
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
      form.elements.reviewed_hash.value=data.hash||'';button.textContent=data.label||'Confirm arrival';const unsavedPaper=Boolean(form.querySelector('[name="paper-paper_signed"]')?.checked);
      button.disabled=!data.can_confirm||unsavedPaper;
      status.textContent=unsavedPaper?'Save the paper-waiver details before completing arrival.':data.can_confirm?'':'Confirm waiver coverage to finish arrival.';
    }catch(e){if(e.name!=='AbortError'&&serial===generation)status.textContent=e.message;}
  };
  form.addEventListener('input',event=>{if(event.target.form!==form)return;button.disabled=true;clearTimeout(timer);timer=setTimeout(update,250);});
  form.addEventListener('change',event=>{if(event.target.form!==form)return;sync();button.disabled=true;clearTimeout(timer);timer=setTimeout(update,80);});
  form.addEventListener('submit',e=>{if(button.disabled||!form.elements.reviewed_hash.value){e.preventDefault();update();}});
  window.addEventListener('focus',()=>update());
  const paperForm=document.querySelector('[data-arrival-paper-form]');
  const paperEntry=form.querySelector('[data-arrival-paper-entry]');
  if(paperForm&&paperEntry){
    const check=paperForm.elements.namedItem('paper-paper_signed');
    const fields=paperEntry.querySelector('[data-arrival-paper-fields]');
    const save=paperEntry.querySelector('[data-save-arrival-paper]');
    const paperStatus=paperEntry.querySelector('[data-arrival-paper-status]');
    const syncPaper=()=>{fields.hidden=!check.checked;save.disabled=!check.checked;for(const input of fields.querySelectorAll('input,select,textarea'))input.disabled=!check.checked;if(check.checked){button.disabled=true;status.textContent='Save the paper-waiver details before completing arrival.';}};
    check.addEventListener('change',()=>{syncPaper();if(!check.checked)update();});syncPaper();
    paperForm.addEventListener('submit',async event=>{
      event.preventDefault();save.disabled=true;paperStatus.textContent='Saving paper-waiver record…';
      try{
        const response=await fetch(paperForm.action,{method:'POST',body:new FormData(paperForm),headers:{Accept:'application/json'},cache:'no-store'});
        const data=await response.json();
        if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the paper-waiver details.');
        form.querySelector('[data-arrival-active-waivers]').innerHTML=data.html;
        paperForm.elements.namedItem('paper-request_key').value=crypto.randomUUID();
        paperForm.elements.namedItem('paper-signer_name').value='';paperForm.elements.namedItem('paper-minors').value='';
        check.checked=false;syncPaper();paperStatus.textContent='Paper-waiver record saved. Confirm coverage for everyone before completing arrival.';
        await update();
      }catch(error){paperStatus.textContent=error.message;save.disabled=false;}
    });
  }
  const receiptDialog=document.querySelector('[data-zelle-receipt-dialog]');
  if(receiptDialog){
    form.querySelector('[data-open-zelle-receipt]').addEventListener('click',()=>receiptDialog.showModal());
    receiptDialog.querySelector('[data-close-zelle-receipt]').addEventListener('click',()=>receiptDialog.close());
    const receiptForm=receiptDialog.querySelector('form');
    receiptForm.addEventListener('submit',async event=>{
      event.preventDefault();const save=receiptForm.querySelector('button[type=submit],button:not([type])');save.disabled=true;
      try{
        const response=await fetch(receiptForm.action,{method:'POST',body:new FormData(receiptForm),headers:{Accept:'application/json'}});const data=await response.json();
        if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the receipt.');
        receiptForm.elements.request_key.value=crypto.randomUUID();receiptForm.elements.value.value='';receiptForm.elements.verified.checked=false;
        receiptDialog.close();const notice=document.createElement('p');notice.textContent=`Zelle recorded: $${data.received}`;form.querySelector('[data-open-zelle-receipt]').before(notice);await update();
      }catch(error){receiptDialog.querySelector('[data-zelle-error]').textContent=error.message;}finally{save.disabled=false;}
    });
  }
  sync();
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

for(const form of document.querySelectorAll('form:not([data-arrival-live])')){
 const method=form.elements.method;
 if(!method)continue;
 for(const name of ['received_on','zelle_sender']){
  const field=form.querySelector(`[data-field="${name}"]`);if(!field)continue;
  const sync=()=>{field.hidden=method.value!=='zelle';for(const input of field.querySelectorAll('input'))input.disabled=field.hidden;};
  method.addEventListener('change',sync);sync();
 }
}
