const detectForm = document.getElementById('detectForm');
const encodeForm = document.getElementById('encodeForm');
const decodeForm = document.getElementById('decodeForm');
const encodeSection = document.getElementById('encodeSection');
const decodeSection = document.getElementById('decodeSection');
const tabHide = document.getElementById('tabHide');
const tabReveal = document.getElementById('tabReveal');

const modeSel = document.getElementById('mode');
const textRow = document.getElementById('textRow');
const fileRow = document.getElementById('fileRow');

modeSel.addEventListener('change', () => {
  if (modeSel.value === 'text') {
    textRow.classList.remove('hidden');
    fileRow.classList.add('hidden');
  } else {
    textRow.classList.add('hidden');
    fileRow.classList.remove('hidden');
  }
});

// Tabs: Hide (Encode) / Reveal (Decode)
function setTab(isHide) {
  if (!encodeSection || !decodeSection) return;
  if (isHide) {
    encodeSection.classList.remove('hidden');
    decodeSection.classList.add('hidden');
    tabHide?.classList.add('active');
    tabHide?.setAttribute('aria-selected', 'true');
    tabReveal?.classList.remove('active');
    tabReveal?.setAttribute('aria-selected', 'false');
  } else {
    encodeSection.classList.add('hidden');
    decodeSection.classList.remove('hidden');
    tabReveal?.classList.add('active');
    tabReveal?.setAttribute('aria-selected', 'true');
    tabHide?.classList.remove('active');
    tabHide?.setAttribute('aria-selected', 'false');
  }
}
tabHide?.addEventListener('click', () => setTab(true));
tabReveal?.addEventListener('click', () => setTab(false));

// Dropzone wiring: click opens file dialog; drag/drop assigns file
function wireDropzone(dz) {
  if (!dz) return;
  const inputId = dz.getAttribute('data-for');
  const input = document.getElementById(inputId);
  if (!input) return;
  dz.addEventListener('click', () => input.click());
  ['dragenter','dragover'].forEach(evt => dz.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dz.classList.add('dragover');
  }));
  ['dragleave','drop'].forEach(evt => dz.addEventListener(evt, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dz.classList.remove('dragover');
  }));
  dz.addEventListener('drop', (e) => {
    const files = e.dataTransfer?.files;
    if (files && files.length) {
      input.files = files;
      const changeEvent = new Event('change', { bubbles: true });
      input.dispatchEvent(changeEvent);
    }
  });
}

document.querySelectorAll('.dropzone').forEach(wireDropzone);

// Live character counter for secret text
const secretText = document.getElementById('secretText');
const textCounter = document.getElementById('textCounter');
secretText?.addEventListener('input', () => {
  const len = secretText.value.length;
  if (textCounter) textCounter.textContent = `${len} character${len===1?'':'s'}`;
});

async function postForm(url, formEl) {
  const fd = new FormData(formEl);
  const res = await fetch(url, { method: 'POST', body: fd });
  return res;
}

// Detect
if (detectForm) {
  detectForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pre = document.getElementById('detectResult');
    pre.textContent = 'Detecting...';
    try {
      const res = await postForm('/detect', detectForm);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Detection failed');
      pre.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      pre.textContent = 'Error: ' + err.message;
    }
  });
}

// Encode capacity hint when choosing cover image
const coverInput = encodeForm?.querySelector('input[name="image"]');
coverInput?.addEventListener('change', async () => {
  const capacityInfo = document.getElementById('capacityInfo');
  capacityInfo.textContent = '';
  if (!coverInput.files || coverInput.files.length === 0) return;
  const fd = new FormData();
  fd.append('image', coverInput.files[0]);
  try {
    const res = await fetch('/capacity', { method: 'POST', body: fd });
    const data = await res.json();
    if (res.ok) {
      capacityInfo.textContent = `Capacity: ${data.capacity_bytes} bytes (~${data.capacity_bits} bits)`;
    } else {
      capacityInfo.textContent = 'Capacity check failed: ' + (data.error || 'Unknown');
    }
  } catch (e) {
    capacityInfo.textContent = 'Capacity check failed';
  }
});

// Encode
if (encodeForm) {
  encodeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const res = await postForm('/encode', encodeForm);
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Encode failed');
      }
      // Download image
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stego.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error: ' + err.message);
    }
  });
}

// Decode
if (decodeForm) {
  decodeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pre = document.getElementById('decodeMsg');
    pre.textContent = 'Decoding...';
    try {
      const res = await postForm('/decode', decodeForm);
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Decode failed');
      }
      const disp = res.headers.get('Content-Disposition') || '';
      let filename = 'payload.bin';
      const m = /filename="?([^";]+)"?/i.exec(disp);
      if (m) filename = m[1];
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      pre.textContent = 'Downloaded: ' + filename;
    } catch (err) {
      pre.textContent = 'Error: ' + err.message;
    }
  });
}
