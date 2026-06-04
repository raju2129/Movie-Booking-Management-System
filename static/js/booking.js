/* booking.js */
let qty = 1;
const price = parseFloat(document.getElementById('priceVal')?.value || 0);
const fee   = 30;

function reCalc() {
  const sub   = qty * price;
  const conv  = qty * fee;
  const total = sub + conv;
  document.getElementById('qtyDisplay').textContent = qty;
  document.getElementById('qtyInput').value         = qty;
  document.getElementById('subtotal').textContent   = '₹' + sub.toFixed(0);
  document.getElementById('convenience').textContent= '₹' + conv.toFixed(0);
  document.getElementById('totalDisplay').textContent='₹' + total.toFixed(0);
}

window.incQty = () => { if (qty < 10) { qty++; reCalc(); } };
window.decQty = () => { if (qty > 1)  { qty--; reCalc(); } };
reCalc();

// Payment method
document.querySelectorAll('.pay-card').forEach(c => {
  c.addEventListener('click', () => {
    document.querySelectorAll('.pay-card').forEach(x => x.classList.remove('selected'));
    c.classList.add('selected');
    document.getElementById('payMethod').value = c.dataset.method;
  });
});

// Book submit
const bookForm = document.getElementById('bookForm');
if (bookForm) {
  bookForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('bookBtn');
    const orig = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing…';
    const rows = ['A','B','C','D','E','F'];
    const row  = rows[Math.floor(Math.random()*rows.length)];
    const start = Math.floor(Math.random()*8)+1;
    const seats = Array.from({length:qty}, (_,i) => row+(start+i)).join(', ');
    try {
      const res = await fetch(window.location.href, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ num_tickets:qty, payment_method:document.getElementById('payMethod').value, seat_numbers:seats })
      });
      const d = await res.json();
      if (d.success) { setTimeout(() => location.href = d.redirect, 600); }
      else { alert(d.message || 'Booking failed.'); btn.disabled=false; btn.innerHTML=orig; }
    } catch { alert('Network error.'); btn.disabled=false; btn.innerHTML=orig; }
  });
}

// Cancel
window.cancelBooking = async (id) => {
  if (!confirm('Cancel this booking? This cannot be undone.')) return;
  try {
    const res = await fetch(`/user/booking/${id}/cancel`, { method:'POST', headers:{'Content-Type':'application/json'} });
    const d = await res.json();
    if (d.success) { window.toast?.(d.message,'success'); setTimeout(() => location.reload(), 1200); }
    else alert(d.message);
  } catch { alert('Network error.'); }
};

// Profile save
const profForm = document.getElementById('profileForm');
if (profForm) {
  profForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('saveBtn');
    const orig = btn.innerHTML;
    btn.disabled=true; btn.innerHTML='<span class="spinner-border spinner-border-sm me-1"></span>Saving…';
    try {
      const res = await fetch('/user/profile', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          name:  document.getElementById('pName').value.trim(),
          phone: document.getElementById('pPhone').value.trim(),
          city:  document.getElementById('pCity').value.trim()
        })
      });
      const d = await res.json();
      const div = document.createElement('div');
      div.className=`alert alert-${d.success?'success':'danger'} mt-3 rounded-3`;
      div.textContent = d.message;
      profForm.appendChild(div);
      setTimeout(() => div.remove(), 3000);
    } catch { alert('Network error.'); }
    btn.disabled=false; btn.innerHTML=orig;
  });
}
