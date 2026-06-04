/* admin.js */
async function submitAddOwner() {
  const form = document.getElementById('addOwnerForm');
  const payload = {
    name:  form.querySelector('[name="name"]').value.trim(),
    email: form.querySelector('[name="email"]').value.trim(),
    phone: form.querySelector('[name="phone"]')?.value.trim() || '',
    city:  form.querySelector('[name="city"]')?.value.trim() || ''
  };
  if (!payload.name || !payload.email) { window.toast('Name and email are required.', 'danger'); return; }
  const btn = document.getElementById('addOwnerBtn');
  const orig = btn.innerHTML;
  btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Creating…';
  try {
    const res = await fetch('/admin/theatre-owners/create', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    const d = await res.json();
    if (d.success) {
      window.toast('Theatre owner created!', 'success');
      const box = document.getElementById('credBox');
      if (box && d.credentials) {
        document.getElementById('credEmail').textContent = d.credentials.email;
        document.getElementById('credPass').textContent  = d.credentials.password;
        box.classList.remove('d-none');
      }
      form.reset();
      setTimeout(() => location.reload(), 3500);
    } else { window.toast(d.message || 'Failed.', 'danger'); }
  } catch { window.toast('Network error.', 'danger'); }
  btn.disabled = false; btn.innerHTML = orig;
}

async function toggleOwner(id) {
  try {
    const res = await fetch(`/admin/theatre-owners/${id}/deactivate`, { method:'POST', headers:{'Content-Type':'application/json'} });
    const d = await res.json();
    if (d.success) { window.toast(d.message, 'success'); setTimeout(() => location.reload(), 1200); }
  } catch { window.toast('Network error.', 'danger'); }
}

// Table search on Enter
document.querySelectorAll('.tbl-search').forEach(inp => {
  inp.addEventListener('keyup', e => {
    if (e.key !== 'Enter') return;
    const url = new URL(window.location);
    url.searchParams.set('search', inp.value);
    url.searchParams.set('page','1');
    window.location.href = url.toString();
  });
});
