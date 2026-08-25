// Customer order tracking + live map

let map = null;
let deliveryMarker = null;
let pollInterval = null;

const STATUS_ORDER = [
  'PENDING',
  'APPROVED',
  'PREPARING',
  'ASSIGNED',
  'OUT_FOR_DELIVERY',
  'DELIVERED'
];

function initTrackingMap(orderNumber, customerLat, customerLng) {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  // Default center: Ratuwamai area approx
  const defaultLat = customerLat || 26.65;
  const defaultLng = customerLng || 87.55;

  map = L.map('map').setView([defaultLat, defaultLng], 14);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  }).addTo(map);

  if (customerLat && customerLng) {
    L.marker([customerLat, customerLng], {
      icon: L.divIcon({
        className: 'custom-marker',
        html: '<div style="background:#e85d04;color:#fff;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3)">📍</div>',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      })
    }).addTo(map).bindPopup('Your delivery address');
  }

  // Start polling
  pollLocation(orderNumber);
  pollInterval = setInterval(() => pollLocation(orderNumber), 8000);
}

async function pollLocation(orderNumber) {
  try {
    const res = await fetch(`/api/orders/${orderNumber}/location`);
    const data = await res.json();
    if (!data.ok) return;

    // Update status display if needed
    const statusEl = document.getElementById('currentStatus');
    if (statusEl && data.status) {
      statusEl.textContent = data.status.replace(/_/g, ' ');
    }

    const infoEl = document.getElementById('mapInfo');
    if (!data.has_location) {
      if (infoEl) {
        infoEl.textContent = data.status === 'OUT_FOR_DELIVERY'
          ? 'Waiting for delivery boy to share location…'
          : 'Live tracking available when order is Out for Delivery.';
      }
      return;
    }

    const lat = data.latitude;
    const lng = data.longitude;
    const updated = data.updated_at ? new Date(data.updated_at).toLocaleTimeString() : '';

    if (infoEl) {
      let extra = '';
      if (data.distance_km != null && data.eta_minutes != null) {
        extra = ` · ~${data.distance_km} km · ≈ ${data.eta_minutes} min away`;
      }
      infoEl.textContent = `🛵 Delivery boy location • Last updated: ${updated}${extra}`;
    }

    if (!map) return;

    if (deliveryMarker) {
      deliveryMarker.setLatLng([lat, lng]);
    } else {
      deliveryMarker = L.marker([lat, lng], {
        icon: L.divIcon({
          className: 'custom-marker',
          html: '<div style="background:#0077b6;color:#fff;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.35)">🛵</div>',
          iconSize: [36, 36],
          iconAnchor: [18, 18]
        })
      }).addTo(map).bindPopup(data.delivery_boy_name || 'Delivery Boy');
    }

    // Fit bounds if both points exist
    if (data.customer_lat && data.customer_lng) {
      map.fitBounds([
        [lat, lng],
        [data.customer_lat, data.customer_lng]
      ], { padding: [40, 40] });
    } else {
      map.setView([lat, lng], 15);
    }
  } catch (e) {
    console.warn('Location poll failed', e);
  }
}

// Cleanup on leave
window.addEventListener('beforeunload', () => {
  if (pollInterval) clearInterval(pollInterval);
});
