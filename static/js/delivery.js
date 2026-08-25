// Delivery boy GPS sharing + approximate ETA

let watchId = null;
let activeOrderId = null;

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function formatEta(distanceKm, speedKmh) {
  if (distanceKm == null || distanceKm < 0 || !speedKmh) return null;
  let minutes = Math.round((distanceKm / speedKmh) * 60);
  minutes = Math.max(1, Math.min(120, minutes));
  if (minutes < 60) return `≈ ${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `≈ ${h}h ${m}min` : `≈ ${h}h`;
}

function updateEtaDisplay(lat, lng, serverData) {
  const etaEl = document.getElementById('etaStatus');
  if (!etaEl) return;

  let distanceKm = null;
  let etaMinutes = null;

  if (serverData && serverData.distance_km != null) {
    distanceKm = serverData.distance_km;
    etaMinutes = serverData.eta_minutes;
  } else if (
    typeof window.CUSTOMER_LAT === 'number' &&
    typeof window.CUSTOMER_LNG === 'number' &&
    lat != null &&
    lng != null
  ) {
    distanceKm = haversineKm(lat, lng, window.CUSTOMER_LAT, window.CUSTOMER_LNG);
    distanceKm = Math.round(distanceKm * 100) / 100;
    const speed = window.AVG_SPEED_KMH || 18;
    etaMinutes = Math.max(1, Math.min(120, Math.round((distanceKm / speed) * 60)));
  }

  if (distanceKm != null) {
    const etaText =
      etaMinutes != null
        ? formatEta(distanceKm, (distanceKm / etaMinutes) * 60) || `≈ ${etaMinutes} min`
        : '';
    etaEl.textContent = `🛣️ ~${distanceKm} km away · ${etaText} to customer`;
    etaEl.style.color = 'var(--primary)';
  } else if (window.CUSTOMER_LAT == null) {
    etaEl.textContent = 'Customer GPS not shared — ETA unavailable';
    etaEl.style.color = '#6b7280';
  } else {
    etaEl.textContent = '';
  }
}

function startLocationShare(orderId) {
  if (!navigator.geolocation) {
    showToast('GPS not supported on this device');
    return;
  }
  activeOrderId = orderId;
  const statusEl = document.getElementById('gpsStatus');
  if (statusEl) statusEl.textContent = 'Requesting location permission…';

  watchId = navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      if (statusEl) {
        statusEl.textContent = `📍 Sharing location (${latitude.toFixed(5)}, ${longitude.toFixed(5)})`;
        statusEl.style.color = '#2d6a4f';
      }
      sendLocation(orderId, latitude, longitude);
      // Client-side ETA while waiting for server response
      updateEtaDisplay(latitude, longitude, null);
    },
    (err) => {
      let msg = 'Location error';
      if (err.code === 1) msg = 'Permission denied. Please allow location access.';
      else if (err.code === 2) msg = 'GPS unavailable. Check device settings.';
      else if (err.code === 3) msg = 'Location request timed out.';
      if (statusEl) {
        statusEl.textContent = msg;
        statusEl.style.color = '#c1121f';
      }
      showToast(msg);
    },
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 15000
    }
  );

  // Also update status to OUT_FOR_DELIVERY
  updateOrderStatus(orderId, 'OUT_FOR_DELIVERY');
  showToast('Location sharing started');
}

function stopLocationShare() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
  activeOrderId = null;
  const statusEl = document.getElementById('gpsStatus');
  if (statusEl) {
    statusEl.textContent = 'Location sharing stopped';
    statusEl.style.color = '';
  }
  const etaEl = document.getElementById('etaStatus');
  if (etaEl) etaEl.textContent = '';
  showToast('Location sharing stopped');
}

async function sendLocation(orderId, lat, lng) {
  try {
    const res = await fetch('/api/delivery/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_id: orderId,
        latitude: lat,
        longitude: lng
      })
    });
    const data = await res.json();
    if (data && data.ok) {
      updateEtaDisplay(lat, lng, data);
    }
  } catch (e) {
    console.warn('Failed to send location', e);
  }
}

async function updateOrderStatus(orderId, status) {
  try {
    const res = await fetch('/api/delivery/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_id: orderId, status })
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`Status: ${status.replace(/_/g, ' ')}`);
      setTimeout(() => window.location.reload(), 800);
    } else {
      showToast(data.error || 'Could not update status');
    }
  } catch (e) {
    showToast('Network error');
  }
}

function markDelivered(orderId) {
  if (!confirm('Mark this order as Delivered?')) return;
  stopLocationShare();
  updateOrderStatus(orderId, 'DELIVERED');
}
