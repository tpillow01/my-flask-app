// Install prompt
let deferredPrompt;
const installBtn = document.getElementById('installBtn');
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault(); deferredPrompt = e; if (installBtn) installBtn.hidden = false;
});
installBtn?.addEventListener('click', async () => { if (!deferredPrompt) return; deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt = null; });

// Greeting + hero
const mechInput = document.getElementById('mechanic');
const vanField = document.getElementById('van_id'); // works for <select> or <input>
const heroVan = document.getElementById('heroVan');
const greeting = document.getElementById('greeting');
const startBtn = document.getElementById('startBtn');
const scrollToForm = document.getElementById('scrollToForm');

function updateGreeting(){
  if (!greeting) return;
  const name = (mechInput?.value || 'Mechanic').trim();
  const h = new Date().getHours(); const sal = h<12?'Good morning':h<18?'Good afternoon':'Good evening';
  greeting.textContent = `${sal}, ${name || 'Mechanic'}`;
}
function updateHeroVan(){
  if (heroVan && vanField) heroVan.textContent = vanField.value || '—';
}
mechInput?.addEventListener('input', updateGreeting);
// Support both select and input for the van field
vanField?.addEventListener('change', updateHeroVan);
vanField?.addEventListener('input', updateHeroVan);

document.addEventListener('DOMContentLoaded', () => { updateGreeting(); updateHeroVan(); });

startBtn?.addEventListener('click', () => {
  const f = document.querySelector('form'); if (f) window.scrollTo({ top: f.offsetTop - 10, behavior: 'smooth' });
});
scrollToForm?.addEventListener('click', () => {
  const f = document.querySelector('form'); if (f) window.scrollTo({ top: f.offsetTop - 10, behavior: 'smooth' });
});

// Rings
const checksRing = document.getElementById('checksRing');
const checksRingText = document.getElementById('checksRingText');
function updateChecksRing(){
  const boxes = Array.from(document.querySelectorAll('.checks input[type="checkbox"]'));
  const total = boxes.length || 1;
  const done = boxes.filter(b => b.checked).length;
  if (checksRing) checksRing.style.setProperty('--val', String(done/total));
  if (checksRingText) checksRingText.innerHTML = `${done}/${total}<br><small>checks</small>`;
}
document.querySelectorAll('.checks input[type="checkbox"]').forEach(cb => cb.addEventListener('change', updateChecksRing));
document.addEventListener('DOMContentLoaded', updateChecksRing);

const fuel = document.getElementById('fuel');
const fuelRing = document.getElementById('fuelRing');
const fuelRingText = document.getElementById('fuelRingText');
function updateFuelRing(){
  const pct = fuel ? Number(fuel.value) : 0;
  if (fuelRing) fuelRing.style.setProperty('--val', String(pct/100));
  if (fuelRingText) fuelRingText.textContent = `${pct}%`;
}
fuel?.addEventListener('input', updateFuelRing);
document.addEventListener('DOMContentLoaded', updateFuelRing);

// Offline queue for true offline only
const statusEl = document.getElementById('status');
const statusBar = document.getElementById('statusBar');
const statusBarText = document.getElementById('statusBarText');

const DB_NAME = 'van-checklist-db'; const STORE = 'pending';
function openDB(){
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath:'id', autoIncrement:true });
    req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
  });
}
async function queuePending(payload){
  const db = await openDB();
  const tx = db.transaction(STORE, 'readwrite'); tx.objectStore(STORE).add(payload); await tx.done;
}
async function flushPending(){
  try {
    const db = await openDB(); const tx = db.transaction(STORE, 'readwrite'); const store = tx.objectStore(STORE);
    const getAllReq = store.getAll();
    getAllReq.onsuccess = async () => {
      const items = getAllReq.result || [];
      for (const it of items) {
        try {
          const res = await fetch('/api/submit', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(it.payload) });
          if (res.ok) store.delete(it.id);
        } catch {}
      }
    };
  } catch {}
}
function setOnline(val){
  if (!statusBar) return;
  if (val) { statusBarText.textContent = 'Online'; statusBar.hidden = false; setTimeout(()=> statusBar.hidden = true, 1500); flushPending(); }
  else { statusBarText.textContent = 'Offline — will sync'; statusBar.hidden = false; }
}
window.addEventListener('online',  () => setOnline(true));
window.addEventListener('offline', () => setOnline(false));
document.addEventListener('DOMContentLoaded', () => setOnline(navigator.onLine));

// Submit handler
const form = document.getElementById('checklistForm');
function toBool(v){ return !!v; }
form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const payload = {
    shift: fd.get('shift'),
    mechanic: (fd.get('mechanic') || '').trim(),
    van_id: fd.get('van_id'),
    odometer: fd.get('odometer') ? Number(fd.get('odometer')) : null,
    fuel_level: fd.get('fuel_level') ? Number(fd.get('fuel_level')) : null,
    interior_clean: toBool(fd.get('interior_clean')),
    trash_removed: toBool(fd.get('trash_removed')),
    tools_secured: toBool(fd.get('tools_secured')),
    tires_ok: toBool(fd.get('tires_ok')),
    lights_ok: toBool(fd.get('lights_ok')),
    fluids_ok: toBool(fd.get('fluids_ok')),
    windshield_clean: toBool(fd.get('windshield_clean')),
    wiper_fluid_ok: toBool(fd.get('wiper_fluid_ok')),
    horn_ok: toBool(fd.get('horn_ok')),
    seatbelts_ok: toBool(fd.get('seatbelts_ok')),
    first_aid_present: toBool(fd.get('first_aid_present')),
    fire_extinguisher_present: toBool(fd.get('fire_extinguisher_present')),
    backup_camera_ok: toBool(fd.get('backup_camera_ok')),
    registration_present: toBool(fd.get('registration_present')),
    turn_signals_ok: toBool(fd.get('turn_signals_ok')),
    brake_lights_ok: toBool(fd.get('brake_lights_ok')),
    spare_tire_present: toBool(fd.get('spare_tire_present')),
    jack_present: toBool(fd.get('jack_present')),
    notes: (fd.get('notes') || '').trim()
  };

  try {
    const res = await fetch('/api/submit', {
      method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });

    if (res.status === 401 || res.redirected) {
      statusEl.textContent = 'Please sign in first.'; statusEl.className = 'status error';
      window.location.href = '/auth?next=/';
      return;
    }

    // If the checklist failed, queue it offline
    if (!res.ok) {
      await queuePending({ payload });
      statusEl.textContent = 'Saved offline. Will sync when online.';
      statusEl.className = 'status offline';
      setOnline(false);
      return;
    }

    // ✅ Checklist saved; get entry id
    const data = await res.json();
    if (!data?.ok || !data?.id) {
      statusEl.textContent = 'Error saving (no id returned).';
      statusEl.className = 'status error';
      return;
    }

    // 🔹 NEW: Upload photos if selected
    const photosInput = document.getElementById('photos');
    if (photosInput && photosInput.files && photosInput.files.length > 0) {
      try {
        statusEl.textContent = `Uploading ${photosInput.files.length} photo(s)…`;
        statusEl.className = 'status';
        const photoFD = new FormData();
        for (const f of photosInput.files) photoFD.append('photos', f);
        const up = await fetch(`/api/entries/${data.id}/photos`, { method: 'POST', body: photoFD });
        const upData = await up.json().catch(() => ({}));
        if (!up.ok || !upData?.ok) {
          statusEl.textContent = 'Checklist saved; photo upload failed.';
          statusEl.className = 'status error';
        }
      } catch {
        // If offline or failed, we keep the checklist saved and notify about photos only
        statusEl.textContent = 'Checklist saved; photos will not upload offline.';
        statusEl.className = 'status offline';
      }
    }

    // Done
    statusEl.textContent = 'Saved ✓';
    statusEl.className = 'status ok';
    form.reset();
    updateFuelRing();
    updateChecksRing();
    updateGreeting();
    updateHeroVan();
  } catch {
    await queuePending({ payload });
    statusEl.textContent = 'Saved offline. Will sync when online.';
    statusEl.className = 'status offline';
    setOnline(false);
  }
});
