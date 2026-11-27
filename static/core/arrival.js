// Arrival previews and drafts never record money. Only the final explicit submit does.
for (const form of document.querySelectorAll('[data-arrival-live]')) {
  const button=form.querySelector('[data-arrival-confirm]'), status=form.querySelector('[data-arrival-status]');
  const label=button.querySelector('[data-arrival-button-label]'), dots=button.querySelector('.processing-dots');
  const rowHost=form.querySelector('[data-payment-rows]'), add=form.querySelector('[data-add-payment]');
  const splitBox=form.querySelector('[data-split-payments]'), rowState=form.querySelector('[data-split-rows]');
  const kinds={cash:'Cash',check:'Check',zelle:'Zelle',gift_card:'Gift card'};
  let heldReceipts={};try{heldReceipts=JSON.parse(form.dataset.heldReceipts||'{}');}catch{}
  const paperForm=document.querySelector('[data-arrival-paper-form]');
  const compedMethods=form.elements.method.dataset.compedMembershipMethods;
  let compedMembershipActive,compedMembershipMethod=form.elements.method.value==='comped'?'':form.elements.method.value;
  let timer,generation=0,finalizing=false,departing=false,pending=Promise.resolve(),lastQuote={},previousMethod=form.elements.method.value,statusUrl,lastRequestedInput='';
  const memberCard=window.MonkeyDoArrivalCard?.(form,()=>update());
  if(memberCard){const address=new URL(location.href);address.searchParams.set('draft',form.elements.arrival_draft.value);history.replaceState(null,'',address);}
  const cents=value=>Math.round(Number(value||0)*100);
  const invalidateReceipts=()=>{
    const member=form.elements.member_add?.checked;
    if(!member&&!form.elements.visit_credit)return;
    if(member){form.elements.member_received.checked=false;form.elements.member_zelle_verified.checked=false;}
    if(['gift_card','split'].includes(form.elements.method.value))form.elements.gift_card_verified.checked=false;
    if(form.elements.method.value==='split')form.elements.zelle_verified.checked=false;
  };
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
    remove.addEventListener('click',()=>{invalidateReceipts();row.remove();serialize();schedule();});
    fill.addEventListener('click',async()=>{
      invalidateReceipts();
      input.value='';serialize();const requested=inputIdentity(payload());await update();
      if(!row.isConnected||inputIdentity(payload())!==requested)return;
      if(!lastQuote.noncard_total)return;
      const other=rows().filter(item=>item!==row).reduce((sum,item)=>sum+cents(item.querySelector('input').value),0);
      input.value=(Math.max(0,cents(lastQuote.noncard_total)-cents(lastQuote.prepaid_available)-cents(form.elements.visit_credit?.value)-other)/100).toFixed(2);
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
    if(compedMethods){
      const active=form.elements.member_add.checked;
      if(active!==compedMembershipActive){
        if(!active&&compedMembershipActive)compedMembershipMethod=form.elements.method.value;
        const choices=active?JSON.parse(compedMethods):[['comped','Owner-comped booking — no payment']];
        form.elements.method.replaceChildren(...choices.map(([value,text])=>new Option(text,value)));
        form.elements.method.value=active?compedMembershipMethod:'comped';
        compedMembershipActive=active;
      }
      form.querySelector('[data-arrival-field="method"] label').textContent=active?'Membership payment (visit is owner-comped):':'Actual payment:';
    }
    const method=form.elements.method.value;
    const splitMember=Boolean(form.elements.member_add?.checked&&method==='split');
    const firstTender=splitMember?(form.elements.member_first_method.value||'cash'):method;
    const memberSplit=splitMember&&firstTender==='split';
    const memberParts=Object.fromEntries(Object.keys(kinds).map(kind=>[kind,memberSplit?cents(form.elements['member_'+kind+'_amount'].value):0]));
    const memberDue=(lastQuote.membership_due_today!=='0.00'||cents(form.elements.member_recorded_zelle?.value)>0)&&!form.elements.member_comped?.checked;
    const giftLabel=form.querySelector('[data-arrival-field="gift_card_verified"] label');
    if(giftLabel)giftLabel.textContent=splitMember?'All physical gift-card amounts shown have been presented and verified.':form.elements.member_add?.checked&&method==='gift_card'?'The physical gift card has been presented and verified for the combined amount shown.':'The physical gift card has been presented and verified.';
    const memberFields=form.querySelector('[data-arrival-membership-fields]');
    if(memberFields){
      const active=form.elements.member_add.checked;
      memberFields.hidden=!active;
      for(const input of memberFields.querySelectorAll('input,select,textarea'))input.disabled=!active;
      const first=form.querySelector('[data-arrival-field="member_first_method"]');
      first.hidden=!splitMember||!memberDue;form.elements.member_first_method.disabled=!splitMember;
      const firstParts=memberFields.querySelector('[data-membership-first-split]');
      firstParts.hidden=!memberSplit||!memberDue;
      for(const field of firstParts.querySelectorAll('[data-arrival-field]')){field.hidden=firstParts.hidden;for(const input of field.querySelectorAll('input'))input.disabled=firstParts.hidden;}
      const recorded=memberFields.querySelector('[data-membership-recorded-zelle]');
      recorded.hidden=!memberSplit||!(cents(lastQuote.membership_zelle_available??recorded.dataset.available)||cents(form.elements.member_recorded_zelle.value));
      form.elements.member_recorded_zelle.disabled=recorded.hidden;
      const card=memberFields.querySelector('[data-membership-monthly-card]');
      const needsCard=active&&!form.elements.member_comped?.checked&&(lastQuote.membership_needs_card??(form.elements.member_billing.value==='monthly'||['card','split'].includes(firstTender)));
      card.hidden=!needsCard;form.elements.member_card.disabled=!needsCard;
      const entry=memberFields.querySelector('[data-arrival-membership-card]');if(entry)entry.hidden=!needsCard;
      const email=memberFields.querySelector('[data-membership-comped-email]');
      if(email){email.hidden=!form.elements.member_comped.checked;form.elements.member_send_confirmation.disabled=!active||email.hidden;}
      const receipt=form.querySelector('[data-arrival-field="member_received"]');
      receipt.querySelector('label').textContent=splitMember?'The membership cash or check payment shown was actually received.':'The combined cash or check amount shown was actually received.';
      receipt.hidden=['card','gift_card','zelle'].includes(firstTender)||(memberSplit&&!(memberParts.cash+memberParts.check))||(splitMember&&!memberDue);form.elements.member_received.disabled=!active||receipt.hidden;
      const bank=memberFields.querySelector('[data-membership-zelle]');
      bank.hidden=!splitMember||!memberDue||!(firstTender==='zelle'||(memberSplit&&memberParts.zelle));
      for(const field of bank.querySelectorAll('[data-arrival-field]')){field.hidden=bank.hidden;for(const input of field.querySelectorAll('input'))input.disabled=bank.hidden;}
      if(!compedMethods)form.querySelector('[data-arrival-field="method"] label').textContent=splitMember?'Visit payment:':'Actual payment:';
    }
    const splitNote=form.querySelector('[data-split-membership-note]');if(splitNote)splitNote.hidden=!splitMember;
    if(form.elements.visit_credit){
      const methodField=form.querySelector('[data-arrival-field="method"]');
      const credited=cents(form.elements.visit_credit.value)>0&&!form.elements.member_add?.checked;
      methodField.hidden=credited&&Boolean(lastQuote.plan?.length)&&lastQuote.plan.every(part=>part.tender==='credit'||part.advance);
      if(!form.elements.member_add?.checked&&!compedMethods)methodField.querySelector('label').textContent=credited?'Remaining payment:':'Actual payment:';
    }
    splitBox.hidden=method!=='split';
    if(method==='split'&&!rows().length)makeRow();
    if(method==='split')serialize();
    const visitGift=lastQuote.plan===undefined||lastQuote.plan.some(part=>part.tender==='gift_card'&&cents(part.amount)>0);
    const values=totals(),zelle=method==='split'&&values.zelle>cents(heldReceipts.zelle),gift=(method==='gift_card'&&visitGift)||(method==='split'&&values.gift_card>cents(heldReceipts.gift_card))||(form.elements.member_add?.checked&&memberDue&&(firstTender==='gift_card'||memberParts.gift_card>0));
    for(const field of form.querySelectorAll('[data-noncard-fields] [data-arrival-field]')){
      const visible={zelle_verified:zelle,gift_card_verified:gift,received_on:zelle,zelle_sender:zelle}[field.dataset.arrivalField];
      field.hidden=!visible;for(const input of field.querySelectorAll('input,select'))input.disabled=!visible;
    }
    for(const kind of Object.keys(kinds))form.elements[kind+'_amount'].disabled=method!=='split';
    memberCard?.sync(lastQuote);
  };
  const payload=()=>{
    const data=new FormData(form);
    if(paperForm)for(const [key,value] of new FormData(paperForm))if(key.startsWith('paper-'))data.set(key,value);
    return data;
  };
  const inputIdentity=data=>JSON.stringify([...data].filter(([name])=>name!=='reviewed_hash'));
  const applyFeedback=(data,ok)=>{
    lastQuote={...lastQuote,...data};
    if(data.held_receipts){
      if(JSON.stringify(heldReceipts)!==JSON.stringify(data.held_receipts))for(const name of ['zelle_verified','gift_card_verified'])form.elements[name].checked=false;
      heldReceipts=data.held_receipts;
    }
    if(data.pending_funds_html&&form.querySelector('[data-pending-funds]'))form.querySelector('[data-pending-funds]').innerHTML=data.pending_funds_html;
    sync();
    if(data.html)form.querySelector('[data-arrival-price]').innerHTML=data.html;
    const terms=form.querySelector('[data-arrival-membership-terms]');
    if(terms)terms.textContent=data.membership_terms||'';
    form.elements.reviewed_hash.value=ok?data.hash||'':'';
    label.textContent=data.label||'Confirm arrival';
    const warning=form.querySelector('[data-waiver-mismatch]');
    warning.hidden=!(data.waiver?.mismatch&&form.elements.waiver_confirmed.value==='yes');
    for(const input of warning.querySelectorAll('input'))input.disabled=warning.hidden;
    const unsavedPaper=Boolean(form.querySelector('[name="paper-paper_signed"]')?.checked);
    button.disabled=!ok||!data.can_confirm||unsavedPaper||Boolean(form.elements.member_add?.checked&&memberCard?.blocked);
    if(!ok)status.textContent=Object.values(data.errors||{}).flat().map(e=>e.message).join(' ')||'Review the details above.';
    else if(unsavedPaper)status.textContent='Save the paper-waiver details before completing arrival.';
    else if(form.elements.waiver_confirmed.value==='no')status.textContent='Complete waiver coverage before confirming arrival.';
    else if(form.elements.waiver_confirmed.value!=='yes')status.textContent='The waiver confirmation field is required.';
    else if(!warning.hidden&&form.elements.waiver_mismatch_accepted.value!=='yes')status.textContent='Review the waiver-count warning before completing arrival.';
    else if(data.membership_ready===false)status.textContent=form.elements.method.value==='split'&&form.elements.member_first_method?.value==='zelle'?'Verify the separate membership Zelle transfer and review the current membership terms.':'Review the membership terms, saved installment card and combined payment confirmation above.';
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
  const schedule=()=>{if(finalizing||departing||inputIdentity(payload())===lastRequestedInput)return;button.disabled=true;clearTimeout(timer);timer=setTimeout(update,200);};
  form.prepareReturnDeparture=async()=>{departing=true;clearTimeout(timer);button.disabled=true;await pending;};
  add.addEventListener('click',()=>{const used=new Set(rows().map(row=>row.querySelector('select').value));const next=Object.keys(kinds).find(kind=>!used.has(kind));if(next){makeRow(next);schedule();}});
  form.querySelector('[data-use-visit-credit]')?.addEventListener('click',async()=>{
    const requested=inputIdentity(payload());await update();
    if(inputIdentity(payload())!==requested||!lastQuote.noncard_total)return;
    const limit=lastQuote.credit_limit??Math.max(0,Number(lastQuote.noncard_total)-Number(lastQuote.prepaid_available));
    form.elements.visit_credit.value=(Math.min(cents(lastQuote.credit_available),cents(limit))/100).toFixed(2);
    form.elements.visit_credit.dispatchEvent(new Event('input',{bubbles:true}));
  });
  form.addEventListener('input',event=>{
    if(event.target.form!==form)return;
    if((form.elements.member_add?.checked||form.elements.visit_credit)&&!['member_accepted','member_received','member_zelle_verified','zelle_verified','gift_card_verified','waiver_confirmed','waiver_mismatch_accepted'].includes(event.target.name)){
      invalidateReceipts();
    }
    if(['children','babies'].includes(event.target.name))for(const input of form.querySelectorAll('[name=waiver_mismatch_accepted]'))input.checked=false;
    schedule();
  });
  form.addEventListener('change',event=>{
    if(event.target.form!==form)return;
    if(event.target.name==='member_add'&&['gift_card','split'].includes(form.elements.method.value))form.elements.gift_card_verified.checked=false;
    if(event.target.name==='member_add')form.elements.member_zelle_verified.checked=false;
    if(event.target.name==='member_card'&&form.elements.member_card_authorization)form.elements.member_card_authorization.value='';
    if(form.elements.member_add?.checked&&(event.target.name==='method'||(event.target.name.startsWith('member_')&&!['member_accepted','member_received','member_zelle_verified'].includes(event.target.name)))){
      form.elements.member_accepted.checked=false;form.elements.member_received.checked=false;
      form.elements.member_zelle_verified.checked=false;
      form.elements.gift_card_verified.checked=false;
    }
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
          const funding=data.state==='succeeded'?(Number(data.credit_applied)>0&&Number(data.received)===0?` Credit applied: $${Number(data.credit_applied).toFixed(2)}.`:` Total received: $${Number(data.received).toFixed(2)}.`):'';
          showResult(data.message+funding);return;
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
    clearTimeout(timer);await pending;
    if(memberCard?.needsPreparation()){
      const acceptedReview=lastQuote.membership_card_review,acceptedOffer=lastQuote.membership_card_purchase?.reviewed;
      form.inert=true;button.disabled=true;status.textContent='Saving the reviewed membership card…';
      const saved=await memberCard.prepare();form.inert=false;
      if(!saved){button.disabled=memberCard.blocked;status.textContent='Review the membership card status above before confirming.';return;}
      await update();
      if(lastQuote.membership_card_review!==acceptedReview){
        if(lastQuote.membership_card_purchase?.reviewed!==acceptedOffer){form.elements.member_accepted.checked=false;await update();}
        status.textContent='The visit or membership changed. Review the updated total before confirming again.';return;
      }
      if(button.disabled)return;
    }
    const data=payload();data.set('confirm_review','1');
    finalizing=true;form.inert=true;button.disabled=true;dots.hidden=false;label.textContent='Processing payment';status.textContent='Confirming arrival and the reviewed payment…';
    try{
      const response=await fetch(location.href,{method:'POST',body:data,headers:{Accept:'application/json'},cache:'no-store'});
      const answer=await response.json();
      if(!response.ok||(!answer.confirmed&&!answer.accepted)){finalizing=false;form.inert=false;dots.hidden=true;applyFeedback(answer,false);return;}
      if(answer.pending_membership){location.assign(answer.pending_url);return;}
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
for(const workspace of document.querySelectorAll('[data-membership-arrival-pending]')){
  const message=workspace.querySelector('[data-pending-message]'),check=workspace.querySelector('[data-pending-check]');
  let polling=false,timer,deadline=Date.now()+60000;
  const refresh=async()=>{
    if(polling)return;polling=true;check.disabled=true;
    try{
      const response=await fetch(workspace.dataset.statusUrl,{headers:{Accept:'application/json'},cache:'no-store'});
      if(!response.ok)throw Error();
      const data=await response.json();message.textContent=data.message;
      workspace.querySelector('[data-pending-continue]').hidden=!(data.can_continue&&workspace.dataset.mayRecheck==='true');
      if(data.membership_amount!==undefined)workspace.querySelector('[data-pending-amount]').textContent='$'+Number(data.membership_amount).toFixed(2);
      if(data.membership_received!==undefined)workspace.querySelector('[data-pending-received]').textContent='$'+Number(data.membership_received).toFixed(2);
      if(data.membership_new_received!==undefined&&workspace.querySelector('[data-pending-new-received]'))workspace.querySelector('[data-pending-new-received]').textContent='$'+Number(data.membership_new_received).toFixed(2);
      if(data.membership_balance!==undefined)workspace.querySelector('[data-pending-balance]').textContent='$'+Number(data.membership_balance).toFixed(2);
      if(data.state==='succeeded'){location.assign(data.booking_url);return;}
      if(data.state==='processing'&&Date.now()<deadline)timer=setTimeout(refresh,1500);
    }catch{message.textContent='We could not check the current payment result. Open the saved payment before collecting again.';}
    finally{polling=false;check.disabled=false;}
  };
  check.addEventListener('click',()=>{clearTimeout(timer);deadline=Date.now()+60000;refresh();});
  if(workspace.dataset.state==='processing')refresh();
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

for(const form of document.querySelectorAll('[data-pending-return]')){
  form.addEventListener('submit',async event=>{
    const arrival=document.querySelector('[data-arrival-live]');
    if(!arrival||form.dataset.returnReady)return;
    event.preventDefault();
    await arrival.prepareReturnDeparture();
    for(const name of ['arrival_draft','arrival_fields']){
      let input=form.elements.namedItem(name);
      if(!input){input=document.createElement('input');input.type='hidden';input.name=name;form.append(input);}
      input.value=name==='arrival_draft'?arrival.elements.arrival_draft.value:JSON.stringify(Object.fromEntries(new FormData(arrival)));
    }
    form.dataset.returnReady='1';const submitter=event.submitter;window.setTimeout(()=>form.requestSubmit(submitter),0);
  });
  for(const field of form.querySelectorAll('[name="receipt"],[name="amount"],[name="completed_on"]')){
    for(const event of ['input','change'])field.addEventListener(event,()=>{form.elements.verified_returned.checked=false;});
  }
}
