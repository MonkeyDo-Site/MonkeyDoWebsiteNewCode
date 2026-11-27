/* A credit preview reserves no funds. Only explicit confirmation spends credit. */
(() => {
  const form=document.querySelector('[data-customer-credit]');if(!form)return;
  const field=name=>form.elements[name],button=form.querySelector('[data-credit-confirm]'),error=form.querySelector('[data-credit-error]'),retry=form.querySelector('[data-credit-retry]');
  let generation=0,timer,last=JSON.stringify([field('installment').value,field('value').value]);
  button.disabled=!field('reviewed').value;
  const preview=async()=>{
    const current=++generation,data=new FormData(form);data.set('action','credit_preview');
    try{
      const response=await fetch(location.href,{method:'POST',body:data,headers:{'X-CSRFToken':field('csrfmiddlewaretoken').value,Accept:'application/json'},cache:'no-store'});
      const result=await response.json();if(current!==generation)return;
      if(!response.ok)throw new Error(result.error||'Review the current credit amount.');
      form.querySelector('[data-credit-review]').innerHTML=result.html;
      retry.hidden=true;field('reviewed').value=result.fingerprint;button.textContent=`Apply customer credit — $${result.amount}`;error.hidden=true;button.disabled=false;
    }catch(failure){if(current!==generation)return;error.textContent=(failure instanceof SyntaxError||failure instanceof TypeError)?'The credit review could not be loaded. Please try again.':failure.message||'The credit review could not be loaded. Please try again.';error.hidden=false;retry.hidden=false;button.disabled=true;}
  };
  retry.addEventListener('click',()=>{button.disabled=true;preview();});
  const changed=()=>{const next=JSON.stringify([field('installment').value,field('value').value]);if(next===last)return;last=next;++generation;field('reviewed').value='';button.disabled=true;clearTimeout(timer);timer=setTimeout(preview,180);};
  form.addEventListener('input',changed);form.addEventListener('change',changed);
  form.addEventListener('submit',event=>{if(button.disabled)event.preventDefault();});
})();
