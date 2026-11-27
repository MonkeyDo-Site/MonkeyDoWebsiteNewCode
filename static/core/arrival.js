// Arrival previews and drafts never record money. Only the final explicit submit does.
for (const form of document.querySelectorAll('[data-arrival-live]')) {
  const button=form.querySelector('[data-arrival-confirm]'), status=form.querySelector('[data-arrival-status]');
  const label=button.querySelector('[data-arrival-button-label]'), dots=button.querySelector('.processing-dots');
  const rowHost=form.querySelector('[data-payment-rows]'), add=form.querySelector('[data-add-payment]');
  const splitBox=form.querySelector('[data-split-payments]'), rowState=form.querySelector('[data-split-rows]');
  const kinds={cash:'Cash',check:'Check',zelle:'Zelle',gift_card:'Gift card'};
  const paperForm=document.querySelector('[data-arrival-paper-form]');
  let timer,generation=0,finalizing=false,departing=false,pending=Promise.resolve(),lastQuote={},previousMethod=form.elements.method.value,statusUrl,lastRequestedInput='';
  const cents=value=>Math.round(Number(value||0)*100);
  const rows=()=>[...rowHost.querySelectorAll('[data-payment-row]')];
  const totals=()=>Object.fromEntries(Object.keys(kinds).map(kind=>[kind,rows().filter(row=>row.querySelector('select').value===kind).reduce((sum,row)=>sum+cents(row.querySelector('input').value),0)]));
  const serialize=()=>{
    const values=totals();
    for(const [kind,value] of Object.entries(values))form.elements[kind+'_amount'].value=(value/100).toFixed(2);
    rowState.value=JSON.stringify(rows().map(row=>({method:row.querySelector('select').value,amount:row.querySelector('input').value})));
    const selected=new Set(rows().map(row=>row.querySelector('select').value));
    for(const row of rows())for(const option of row.querySelector('select').options)option.disabled=selected.has(option.value)&&option.value!==row.querySelector('select').value;
    add.disabled=rows().length>=4;
  };
  const makeRow=(method='cash',amount='')=>{
    const row=document.createElement('div');row.className='split-payment-row';row.dataset.paymentRow='';
    const methodLabel=document.createElement('label');methodLabel.textContent='Payment method';
    const select=document.createElement('select');select.setAttribute('aria-label','Split payment method');
    for(const [key,text] of Object.entries(kinds))select.add(new Option(text,key));select.value=method;methodLabel.append(select);
    const amountLabel=document.createElement('label');amountLabel.textContent='Amount received';
    const input=document.createElement('input');input.type='number';input.min='0';input.step='.01';input.inputMode='decimal';input.value=amount;input.setAttribute('aria-label','Split amount received');amountLabel.append(input);
    const fill=document.createElement('button');fill.type='button';fill.className='text-button';fill.textContent='Use remaining balance';
    const remove=document.createElement('button');remove.type='button';remove.className='text-button';remove.textContent='Remove';
    row.append(methodLabel,amountLabel,fill,remove);rowHost.append(row);
    select.addEventListener('change',()=>{input.value='';serialize();});
    remove.addEventListener('click',()=>{row.remove();serialize();schedule();});
    fill.addEventListener('click',async()=>{
      input.value='';serialize();await update();
      if(!lastQuote.noncard_total)return;
      const other=rows().filter(item=>item!==row).reduce((sum,item)=>sum+cents(item.querySelector('input').value),0);
      input.value=(Math.max(0,cents(lastQuote.noncard_total)-cents(lastQuote.prepaid_available)-other)/100).toFixed(2);
      serialize();await update();
    });
    serialize();return row;
  };
  let restored=[];
  try{restored=JSON.parse(rowState.value||'[]');}catch{/* Only bounded local draft metadata is used. */}
  if(!Array.isArray(restored))restored=[];
  const seen=new Set();
  for(const item of restored.slice(0,4))if(item&&kinds[item.method]&&!seen.has(item.method)){seen.add(item.method);makeRow(item.method,String(item.amount||''));}
  if(!rows().length){
    const saved=Object.entries(kinds).map(([kind])=>[kind,form.elements[kind+'_amount'].value]).filter(([,value])=>cents(value)>0);
    for(const [kind,value] of saved)makeRow(kind,value);
  }
  const sync=()=>{
    const method=form.elements.method.value;
    splitBox.hidden=method!=='split';
    if(method==='split'&&!rows().length)makeRow();
    if(method==='split')serialize();
    const values=totals(),zelle=method==='split'&&values.zelle>0,gift=method==='gift_card'||(method==='split'&&values.gift_card>0);
    for(const field of form.querySelectorAll('[data-noncard-fields] [data-arrival-field]')){
      const visible={zelle_verified:zelle,gift_card_verified:gift,received_on:zelle,zelle_sender:zelle}[field.dataset.arrivalField];
      field.hidden=!visible;for(const input of field.querySelectorAll('input,select'))input.disabled=!visible;
    }
    for(const kind of Object.keys(kinds))form.elements[kind+'_amount'].disabled=method!=='split';
  };
  const payload=()=>{
    const data=new FormData(form);
    if(paperForm)for(const [key,value] of new FormData(paperForm))if(key.startsWith('paper-'))data.set(key,value);
    return data;
  };
  const inputIdentity=data=>JSON.stringify([...data].filter(([name])=>name!=='reviewed_hash'));
  const applyFeedback=(data,ok)=>{
    lastQuote={...lastQuote,...data};
    if(data.html)form.querySelector('[data-arrival-price]').innerHTML=data.html;
    form.elements.reviewed_hash.value=ok?data.hash||'':'';
    label.textContent=data.label||'Confirm arrival';
    const warning=form.querySelector('[data-waiver-mismatch]');
    warning.hidden=!(data.waiver?.mismatch&&form.elements.waiver_confirmed.value==='yes');
    for(const input of warning.querySelectorAll('input'))input.disabled=warning.hidden;
    const unsavedPaper=Boolean(form.querySelector('[name="paper-paper_signed"]')?.checked);
    button.disabled=!ok||!data.can_confirm||unsavedPaper;
    if(!ok)status.textContent=Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the details above.';
    else if(unsavedPaper)status.textContent='Save the paper-waiver details before completing arrival.';
    else if(form.elements.waiver_confirmed.value==='no')status.textContent='Complete waiver coverage before confirming arrival.';
    else if(form.elements.waiver_confirmed.value!=='yes')status.textContent='The waiver confirmation field is required.';
    else if(!warning.hidden&&form.elements.waiver_mismatch_accepted.value!=='yes')status.textContent='Review the waiver-count warning before completing arrival.';
    else if(!data.can_confirm)status.textContent='Verify the received Zelle or physical gift card before completing arrival.';
    else status.textContent='';
  };
  const update=()=>{
    if(finalizing)return Promise.resolve();
    const serial=++generation;
    pending=pending.catch(()=>{}).then(async()=>{
    if(finalizing||serial!==generation)return;
    sync();button.disabled=true;status.textContent='Updating price and balance…';
    try{
      const dataToReview=payload();lastRequestedInput=inputIdentity(dataToReview);
      const response=await fetch(location.href,{method:'POST',body:dataToReview,headers:{Accept:'application/json'},cache:'no-store'});
      const data=await response.json();if(serial!==generation||finalizing)return;
      for(const error of form.querySelectorAll('.errorlist'))error.remove();
      applyFeedback(data,response.ok);
    }catch(error){lastRequestedInput='';if(serial===generation)status.textContent='The updated price could not be loaded. Please check your connection and try again.';}
    });
    return pending;
  };
  const schedule=()=>{if(finalizing||inputIdentity(payload())===lastRequestedInput)return;button.disabled=true;clearTimeout(timer);timer=setTimeout(update,200);};
  add.addEventListener('click',()=>{const used=new Set(rows().map(row=>row.querySelector('select').value));const next=Object.keys(kinds).find(kind=>!used.has(kind));if(next){makeRow(next);schedule();}});
  form.addEventListener('input',event=>{
    if(event.target.form!==form)return;
    if(['children','babies'].includes(event.target.name))for(const input of form.querySelectorAll('[name=waiver_mismatch_accepted]'))input.checked=false;
    schedule();
  });
  form.addEventListener('change',event=>{
    if(event.target.form!==form)return;
    if(event.target===form.elements.method){
      if(previousMethod==='split'&&event.target.value!=='split'){
        rowHost.replaceChildren();rowState.value='[]';
        for(const kind of Object.keys(kinds))form.elements[kind+'_amount'].value='';
        for(const name of ['zelle_verified','gift_card_verified'])form.elements[name].checked=false;
      }
      previousMethod=event.target.value;
    }
    sync();schedule();
  });
  const result=form.querySelector('[data-arrival-result]'),resultText=form.querySelector('[data-arrival-result-text]'),checkStatus=form.querySelector('[data-arrival-check-status]');
  const showResult=(message,pending=false)=>{
    if(!pending)label.textContent='Arrival saved';
    result.hidden=false;resultText.textContent=message;checkStatus.hidden=!pending;
    button.hidden=true;dots.hidden=true;status.textContent='';
  };
  const poll=async()=>{
    const deadline=Date.now()+60000;checkStatus.hidden=true;
    while(true){
      try{
        const response=await fetch(statusUrl,{headers:{Accept:'application/json'},cache:'no-store'});
        if(!response.ok)throw Error();
        const data=await response.json();
        if(data.state!=='processing'){
          showResult(data.message+(data.state==='succeeded'?` Total received: $${Number(data.received).toFixed(2)}.`:''));return;
        }
        if(Date.now()>=deadline){showResult('Arrival saved. Card payment is still pending provider confirmation. Check its status before collecting another payment.',true);return;}
      }catch{showResult('Arrival may already be saved. We could not confirm the payment result. Check payment status or open the booking before taking another payment.',true);return;}
      await new Promise(resolve=>setTimeout(resolve,1500));
    }
  };
  checkStatus.addEventListener('click',poll);
  form.addEventListener('submit',async event=>{
    if(event.submitter?.name==='continue_to'){
      if(departing)return;
      event.preventDefault();clearTimeout(timer);form.inert=true;status.textContent='Preserving your arrival entries…';
      await pending;
      if(paperForm)for(const [name,value] of new FormData(paperForm))if(name.startsWith('paper-')){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.append(input);}
      departing=true;form.inert=false;const submitter=event.submitter;window.setTimeout(()=>form.requestSubmit(submitter),0);return;
    }
    event.preventDefault();if(finalizing||button.disabled||!form.reportValidity())return;
    if(!form.elements.reviewed_hash.value){await update();return;}
    clearTimeout(timer);await pending;const data=payload();data.set('confirm_review','1');
    finalizing=true;form.inert=true;button.disabled=true;dots.hidden=false;label.textContent='Processing payment';status.textContent='Confirming arrival and the reviewed payment…';
    try{
      const response=await fetch(location.href,{method:'POST',body:data,headers:{Accept:'application/json'},cache:'no-store'});
      const answer=await response.json();
      if(!response.ok||!answer.confirmed){finalizing=false;form.inert=false;dots.hidden=true;applyFeedback(answer,false);return;}
      statusUrl=answer.status_url;form.inert=false;
      for(const input of form.querySelectorAll('input,select,textarea'))input.disabled=true;
      for(const other of form.querySelectorAll('button[name=continue_to]'))other.disabled=true;
      await poll();
    }catch{form.inert=false;showResult('We could not confirm the response. Open this booking to check arrival and payment before trying again.');}
  });
  window.addEventListener('focus',()=>{if(!finalizing)update();});
  const paperEntry=form.querySelector('[data-arrival-paper-entry]');
  if(paperForm&&paperEntry){
    const check=paperForm.elements.namedItem('paper-paper_signed'),fields=paperEntry.querySelector('[data-arrival-paper-fields]'),save=paperEntry.querySelector('[data-save-arrival-paper]'),paperStatus=paperEntry.querySelector('[data-arrival-paper-status]');
    const syncPaper=()=>{fields.hidden=!check.checked;save.disabled=!check.checked;for(const input of fields.querySelectorAll('input,select,textarea'))input.disabled=!check.checked;if(check.checked){button.disabled=true;status.textContent='Save the paper-waiver details before completing arrival.';}};
    check.addEventListener('change',()=>{syncPaper();if(!check.checked)update();});syncPaper();
    paperForm.addEventListener('submit',async event=>{
      event.preventDefault();save.disabled=true;paperStatus.textContent='Saving paper-waiver record…';
      try{
        const response=await fetch(paperForm.action,{method:'POST',body:new FormData(paperForm),headers:{Accept:'application/json'},cache:'no-store'});const data=await response.json();
        if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the paper-waiver details.');
        form.querySelector('[data-arrival-active-waivers]').innerHTML=data.html;paperForm.elements.namedItem('paper-request_key').value=crypto.randomUUID();
        paperForm.elements.namedItem('paper-signer_name').value='';paperForm.elements.namedItem('paper-minors').value='';check.checked=false;syncPaper();paperStatus.textContent='Paper-waiver record saved. Confirm coverage for everyone before completing arrival.';await update();
      }catch(error){paperStatus.textContent=error.message;save.disabled=false;}
    });
  }
  const receiptDialog=document.querySelector('[data-zelle-receipt-dialog]');
  if(receiptDialog){
    form.querySelector('[data-open-zelle-receipt]').addEventListener('click',()=>receiptDialog.showModal());receiptDialog.querySelector('[data-close-zelle-receipt]').addEventListener('click',()=>receiptDialog.close());
    const receiptForm=receiptDialog.querySelector('form');
    receiptForm.addEventListener('submit',async event=>{
      event.preventDefault();const save=receiptForm.querySelector('button[type=submit],button:not([type])');save.disabled=true;
      try{
        const response=await fetch(receiptForm.action,{method:'POST',body:new FormData(receiptForm),headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok)throw new Error(Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the receipt.');
        receiptForm.elements.request_key.value=crypto.randomUUID();receiptForm.elements.value.value='';receiptForm.elements.verified.checked=false;receiptDialog.close();const notice=document.createElement('p');notice.textContent=`Zelle recorded: $${data.received}`;form.querySelector('[data-open-zelle-receipt]').before(notice);await update();
      }catch(error){receiptDialog.querySelector('[data-zelle-error]').textContent=error.message;}finally{save.disabled=false;}
    });
  }
  sync();update();
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
