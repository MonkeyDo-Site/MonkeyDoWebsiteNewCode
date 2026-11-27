/* Search submits with Enter; valid date/type/status changes apply immediately. */
(() => {
  const form=document.querySelector('[data-membership-filters]');if(!form)return;
  const dates=[...form.querySelectorAll('[data-membership-end-date]')],expiry=form.elements.expiry;
  const sync=()=>{for(const row of dates)row.hidden=expiry.value!=='custom'&&!form.elements.ends_from.value&&!form.elements.ends_to.value;};
  sync();
  form.addEventListener('change',event=>{
    const target=event.target;
    if(target===expiry&&expiry.value==='custom'){sync();form.elements.ends_from.focus();return;}
    if(target===expiry&&expiry.value!=='custom'){form.elements.ends_from.value='';form.elements.ends_to.value='';}
    if(target.matches('input[type=date]')){
      if(!target.validity.valid)return;
      expiry.value='custom';
      const start=form.elements.ends_from.value,end=form.elements.ends_to.value;
      if(start&&end&&start>end)return;
    }
    if(target.matches('select,input[type=date]'))form.requestSubmit();
  });
})();
