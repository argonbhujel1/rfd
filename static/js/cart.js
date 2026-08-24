// Cart operations

async function addToCart(foodId, quantity = 1, instructions = '') {
  try {
    const res = await fetch('/api/cart/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ food_id: foodId, quantity, instructions })
    });
    const data = await res.json();
    if (data.ok) {
      updateCartCount(data.count);
      showToast(data.message || 'Added to cart!');
    } else {
      showToast(data.error || 'Could not add to cart');
    }
  } catch (e) {
    showToast('Network error. Please try again.');
  }
}

async function updateCartQty(foodId, quantity) {
  try {
    const res = await fetch('/api/cart/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ food_id: foodId, quantity })
    });
    const data = await res.json();
    if (data.ok) {
      updateCartCount(data.count);
      if (quantity <= 0) {
        const row = document.querySelector(`[data-food-id="${foodId}"]`);
        if (row) row.remove();
      }
      // Reload page to refresh totals if on cart page
      if (window.location.pathname.includes('/cart')) {
        window.location.reload();
      }
    }
  } catch (e) {
    showToast('Could not update cart');
  }
}

async function removeFromCart(foodId) {
  try {
    const res = await fetch('/api/cart/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ food_id: foodId })
    });
    const data = await res.json();
    if (data.ok) {
      updateCartCount(data.count);
      const row = document.querySelector(`[data-food-id="${foodId}"]`);
      if (row) row.remove();
      if (window.location.pathname.includes('/cart')) {
        window.location.reload();
      }
    }
  } catch (e) {
    showToast('Could not remove item');
  }
}
