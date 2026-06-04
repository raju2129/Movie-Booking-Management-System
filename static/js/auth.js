/* auth.js */
function toast(msg, type) {
  const box = document.getElementById('toastBox');
  if (!box) { alert(msg); return; }
  const colors = { success:'#10b981', danger:'#e5383b' };
  const id = 't' + Date.now();
  box.insertAdjacentHTML('beforeend', `
    <div id="${id}" style="background:${colors[type]||colors.danger};color:#fff;padding:12px 18px;
      border-radius:12px;box-shadow:0 6px 20px rgba(0,0,0,.2);display:flex;align-items:center;
      gap:10px;font-size:.9rem;font-weight:500;min-width:260px;">
      <span style="flex:1">${msg}</span>
      <button onclick="document.getElementById('${id}').remove()" style="background:none;border:none;color:#fff;cursor:pointer;">&times;</button>
    </div>`);
  setTimeout(() => { const el = document.getElementById(id); if (el) el.remove(); }, 4000);
}

function setBtn(btn, loading, orig) {
  btn.disabled = loading;
  btn.innerHTML = loading ? '<span class="spinner-border spinner-border-sm me-2"></span>Please wait...' : orig;
}

// Login
const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    const orig = btn.innerHTML;
    setBtn(btn, true);
    try {
      const res = await fetch('/login', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ email: document.getElementById('email').value.trim(), password: document.getElementById('password').value })
      });
      const d = await res.json();
      if (d.success) { toast('Login successful! Redirecting…', 'success'); setTimeout(() => location.href = d.redirect, 700); }
      else { toast(d.message || 'Invalid credentials.', 'danger'); setBtn(btn, false, orig); }
    } catch { toast('Network error.', 'danger'); setBtn(btn, false, orig); }
  });
}

// Signup
const signupForm = document.getElementById('signupForm');
if (signupForm) {
  signupForm.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('signupBtn');
    const orig = btn.innerHTML;
    const pw = document.getElementById('password').value;
    const cpw = document.getElementById('confirmPassword').value;
    if (pw !== cpw) { toast('Passwords do not match.', 'danger'); return; }
    if (pw.length < 6) { toast('Password must be at least 6 characters.', 'danger'); return; }
    setBtn(btn, true);
    try {
      const res = await fetch('/signup', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          name: document.getElementById('name').value.trim(),
          email: document.getElementById('email').value.trim(),
          password: pw,
          phone: document.getElementById('phone')?.value.trim() || '',
          city: document.getElementById('city')?.value.trim() || ''
        })
      });
      const d = await res.json();
      if (d.success) { toast('Account created!', 'success'); setTimeout(() => location.href = d.redirect, 700); }
      else { toast(d.message || 'Signup failed.', 'danger'); setBtn(btn, false, orig); }
    } catch { toast('Network error.', 'danger'); setBtn(btn, false, orig); }
  });
}

// Eye toggle
document.querySelectorAll('.eye-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const inp = document.getElementById(btn.dataset.target);
    if (!inp) return;
    inp.type = inp.type === 'text' ? 'password' : 'text';
    btn.innerHTML = inp.type === 'text' ? '<i class="fas fa-eye-slash"></i>' : '<i class="fas fa-eye"></i>';
  });
});
