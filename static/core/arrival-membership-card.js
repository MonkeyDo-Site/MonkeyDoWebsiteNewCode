/* Shared membership storage authority; only the arrival submit can request payment. */
window.MonkeyDoArrivalCard = (form, changed) => {
  const section=form.querySelector('[data-membership-card-entry]');
  if(!section)return null;
  const field=name=>form.elements.namedItem(name),status=section.querySelector('[data-member-card-status]');
  const check=section.querySelector('[data-member-card-check]'),frame=section.querySelector('[data-member-new-card]');
  let hosted,quote={},saving=false,uncertain=Boolean(section.dataset.statusUrl),recovering=false;
  let statusUrl=section.dataset.statusUrl,setupKey=crypto.randomUUID();
  let expiredTermsCleared='';
  const report=message=>{status.textContent=message;status.hidden=false;};
  const clearExpiredTerms=id=>{
    if(id&&id!==expiredTermsCleared){expiredTermsCleared=id;field('member_accepted').checked=false;report('Card saved. Its review expired. Review the current terms and confirm to authorize this saved card again.');return true;}
    return false;
  };
  const display=()=>{
    if(![...field('member_card').options].some(item=>item.value==='new'))field('member_card').add(new Option('Enter a new card','new'));
    const fresh=field('member_add').checked&&quote.membership_needs_card!==false&&field('member_card').value==='new';frame.hidden=!fresh;
    for(const input of section.querySelectorAll('[name=member_retain]')){input.disabled=!fresh;input.required=fresh;}
    check.hidden=!uncertain;
  };
  const apply=data=>{
    const select=field('member_card');
    if(![...select.options].some(item=>item.value===data.method_id))select.add(new Option(`${data.brand} ending in ${data.last_four}`,data.method_id));
    select.value=data.method_id;field('member_card_authorization').value=data.authorization_id;
    saving=false;uncertain=false;setupKey=crypto.randomUUID();
    if(data.purchase_recorded){uncertain=true;report('This membership purchase is already recorded. Open its existing record before another payment.');}
    else if(data.authorization_expired)clearExpiredTerms(data.authorization_id);
    else report('Membership card saved. No payment has been requested.');
    display();
  };
  const recover=async()=>{
    if(!statusUrl||recovering)return;recovering=true;
    try{
      const response=await fetch(statusUrl,{headers:{Accept:'application/json'},cache:'no-store'}),data=await response.json();
      if(response.ok&&data.state==='saved'){apply(data);changed();}
      else{uncertain=true;report(data.error||'Check the existing card setup before another attempt.');display();}
    }catch{report('The existing card setup could not be checked. No new exchange or payment was sent.');}
    finally{recovering=false;}
  };
  try{
    hosted=new window.HostedTokenization(JSON.parse(document.querySelector('#membership-card-tokenization-key').textContent),{
      target:'#membership-provider-card-frame',showFieldErrors:true,
      styles:{container:'margin:0;padding:0;min-height:0',cardContainer:'margin:0 8px 0 0',card:'width:100%;box-sizing:border-box',expiryContainer:'margin:0 8px 0 0',cvv2Container:'margin:0',fieldErrors:'color:#9b3650;font-size:12px;margin:4px 0 0'}
    });
  }catch{report('Secure card entry is unavailable. A previously authorized card can still be selected.');}
  check.addEventListener('click',recover);
  let initialCheck=false;
  return {
    get blocked(){return saving||Boolean(uncertain&&quote.membership_needs_card);},
    sync(data){
      quote=data;display();
      if(!uncertain&&quote.membership_card_authorization_expired&&clearExpiredTerms(field('member_card_authorization').value))window.setTimeout(changed,0);
      if(statusUrl&&!initialCheck&&quote.membership_card_purchase){initialCheck=true;recover();}
    },
    needsPreparation(){
      return field('member_add').checked&&quote.membership_needs_card&&(
        field('member_card').value==='new'||(field('member_card_authorization').value&&(quote.membership_card_authorization_expired||quote.membership_card_authorization_offer!==quote.membership_card_purchase?.reviewed))
      );
    },
    async prepare(){
      if(saving||uncertain||!quote.membership_card_purchase||!field('member_accepted').checked)return false;
      saving=true;
      try{
        const payload={purchase:{...quote.membership_card_purchase,accepted:true}};
        if(field('member_card').value==='new'){
          if(!hosted)throw Error('Secure card entry is unavailable.');
          const surcharge=await hosted.getSurcharge();
          if(surcharge.surcharge&&Number(surcharge.surcharge.value)!==0)throw Error('The provider has an additional surcharge configured. Review it before continuing.');
          const token=await hosted.getNonceToken();
          if(!token?.nonce)throw Error('Complete the secure card number, expiration and security code.');
          const retain=field('member_retain').value;
          if(!['yes','no'].includes(retain))throw Error('Choose whether to keep this card for future visits.');
          Object.assign(payload,{setup_key:setupKey,nonce:token.nonce.startsWith('nonce-')?token.nonce:`nonce-${token.nonce}`,expiry_month:token.expiryMonth,expiry_year:token.expiryYear,retention_choice:retain});
          statusUrl=`${section.dataset.statusPrefix}${setupKey}/`;
        }else{payload.method=field('member_card').value;if(quote.membership_card_authorization_expired)payload.previous_authorization=field('member_card_authorization').value;}
        uncertain=true;display();
        const response=await fetch(section.dataset.endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':field('csrfmiddlewaretoken').value},body:JSON.stringify(payload)}),data=await response.json();
        if(response.ok&&data.state==='saved'){apply(data);return !data.purchase_recorded;}
        uncertain=response.status===202;
        report(data.error||'Review the membership card before confirming.');
      }catch(error){report(uncertain?'We could not confirm whether the card was saved. Check card setup before another attempt. No payment has been requested.':error.message);}
      finally{saving=false;display();}
      return false;
    }
  };
};
