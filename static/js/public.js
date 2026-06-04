/* public.js */
function applyFilters() {
  const url = new URL('/', window.location.origin);
  const search = document.getElementById('searchInput')?.value.trim();
  const city   = document.getElementById('citySelect')?.value;
  const genre  = document.getElementById('genreSelect')?.value;
  const lang   = document.getElementById('langSelect')?.value;
  if (search) url.searchParams.set('search', search);
  if (city)   url.searchParams.set('city', city);
  if (genre)  url.searchParams.set('genre', genre);
  if (lang)   url.searchParams.set('language', lang);
  url.searchParams.set('page', '1');
  window.location.href = url.toString();
}

document.getElementById('searchInput')?.addEventListener('keyup', e => { if (e.key === 'Enter') applyFilters(); });
document.getElementById('searchBtn')?.addEventListener('click', applyFilters);
document.getElementById('citySelect')?.addEventListener('change', applyFilters);
document.getElementById('genreSelect')?.addEventListener('change', applyFilters);
document.getElementById('langSelect')?.addEventListener('change', applyFilters);

// Animate cards
const obs = new IntersectionObserver(entries => {
  entries.forEach(en => {
    if (en.isIntersecting) { en.target.style.opacity='1'; en.target.style.transform='translateY(0)'; }
  });
}, { threshold: 0.08 });
document.querySelectorAll('.movie-card').forEach(c => {
  c.style.cssText += 'opacity:0;transform:translateY(20px);transition:opacity .4s ease,transform .4s ease;';
  obs.observe(c);
});

// Auto-scroll to movies section when genre or language filter is active
(function() {
  const params = new URLSearchParams(window.location.search);
  const hasFilter = params.get('genre') || params.get('language');
  if (hasFilter) {
    // Small delay to let page render
    setTimeout(() => {
      const anchor = document.getElementById('grid-anchor');
      if (anchor) {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 120);
  }
})();
