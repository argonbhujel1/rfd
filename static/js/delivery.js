// Delivery boy GPS sharing

let watchId = null;
let activeOrderId = null;

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
  showToast('Location sharing stopped');
}

async function sendLocation(orderId, lat, lng) {
  try {
    await fetch('/api/delivery/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        order_id: orderId,
        latitude: lat,
        longitude: lng
      })
    });
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
