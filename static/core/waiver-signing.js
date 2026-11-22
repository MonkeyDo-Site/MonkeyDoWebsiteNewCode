/* Relationship-specific instructions; the server validates and stores entered names. */
for (const form of document.querySelectorAll('[data-waiver-signing]')) {
  const relationship = form.querySelector('[name=relationship]');
  const minors = form.querySelector('[name=minors]');
  if (!relationship || !minors) continue;
  const label = form.querySelector(`label[for="${minors.id}"]`);
  const help = document.getElementById(`${minors.id}_helptext`);
  const update = () => {
    const role = relationship.value === 'Parent' ? 'parent' : relationship.value === 'Legal guardian' ? 'guardian' : 'default';
    if (label) label.textContent = `${minors.dataset[`${role}Label`]}:`;
    if (help) help.textContent = minors.dataset[`${role}Help`];
  };
  relationship.addEventListener('change', update);
  update();
}
