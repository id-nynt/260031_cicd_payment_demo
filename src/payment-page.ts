export const paymentPage = String.raw`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Payment details - Payment Service</title>
  <script src="https://js.stripe.com/v3/"></script>
  <style>
    *{box-sizing:border-box}
    body{font-family:system-ui,sans-serif;max-width:680px;margin:40px auto;padding:20px;background:#f5f7fb;color:#172033}
    main{background:#fff;padding:30px;border-radius:16px}
    label{display:block;font-weight:600;margin:16px 0 6px}
    input,button{font:inherit;width:100%;padding:12px;border:1px solid #bbc6d6;border-radius:8px}
    button{margin-top:22px;background:#155eef;color:#fff;border:0;font-weight:700;cursor:pointer}
    button:disabled{opacity:.65;cursor:wait}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .summary{background:#f4f6fa;padding:14px;border-radius:8px}
    .message{margin-top:20px;padding:14px;border-radius:8px;background:#fff5d6}
    .message.bad{background:#fdecec;color:#a61b1b}
    [hidden]{display:none!important}
  </style>
</head>
<body>
<main>
  <p><a href="/checkout">Back to checkout</a></p>
  <h1>Payment details</h1>
  <div id="summary" class="summary" aria-live="polite">Loading payment summary...</div>
  <form id="payment-form">
    <section id="fake-fields">
      <label for="card-name">Cardholder name</label>
      <input id="card-name" value="Alex Customer" autocomplete="cc-name" required>
      <label for="card-number">Demo card number</label>
      <input id="card-number" inputmode="numeric" placeholder="4242 4242 4242 4242" autocomplete="cc-number" required>
      <div class="grid">
        <div><label for="expiry">Expiry (MM/YY)</label><input id="expiry" placeholder="12/34" autocomplete="cc-exp" required></div>
        <div><label for="cvc">CVC</label><input id="cvc" placeholder="123" autocomplete="cc-csc" required></div>
      </div>
      <p>Use demo card details only. Full card details are never stored.</p>
    </section>
    <section id="stripe-fields" hidden>
      <label>Stripe payment method</label>
      <div id="stripe-element"></div>
    </section>
    <button id="pay" type="submit">Pay now</button>
  </form>
  <div id="message" class="message" role="status" aria-live="polite" hidden></div>
</main>
<script>
const form = document.getElementById('payment-form');
const payButton = document.getElementById('pay');
const message = document.getElementById('message');
const summary = document.getElementById('summary');
let checkout;
let stripe;
let elements;
let clientSecret;
let paymentId;

function showMessage(text, isError = false) {
  message.textContent = text;
  message.className = isError ? 'message bad' : 'message';
  message.hidden = false;
}
function showError(error) {
  showMessage(error instanceof Error ? error.message : String(error), true);
  payButton.disabled = false;
}
try {
  checkout = JSON.parse(localStorage.getItem('checkoutData') || 'null');
} catch {
  checkout = null;
}
if (!checkout) {
  summary.textContent = 'Checkout information is missing. Please return to checkout.';
  payButton.disabled = true;
  showMessage('Return to checkout to enter customer and amount details.', true);
} else {
  summary.textContent = (checkout.amount / 100).toFixed(2) + ' ' + checkout.currency +
    ' - ' + checkout.payerName + ' - ' + checkout.provider;
  if (checkout.provider === 'stripe') {
    document.getElementById('fake-fields').hidden = true;
    document.getElementById('stripe-fields').hidden = false;
    payButton.disabled = true;
    startStripe();
  }
}

async function startStripe() {
  try {
    const configResponse = await fetch('/config');
    const config = await configResponse.json();
    if (!configResponse.ok || !config.stripeReady) {
      throw new Error('Stripe is not configured. Return to checkout and choose Demo card simulation.');
    }
    if (typeof Stripe !== 'function') {
      throw new Error('Stripe could not load. Check internet access or choose Demo card simulation.');
    }
    stripe = Stripe(config.publishableKey);
    const response = await fetch('/payments/intent', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-' + crypto.randomUUID()},
      body: JSON.stringify(checkout)
    });
    const created = await response.json();
    if (!response.ok) throw new Error(created.message || 'Could not start Stripe payment');
    clientSecret = created.clientSecret;
    paymentId = created.payment.id;
    elements = stripe.elements({clientSecret});
    elements.create('payment').mount('#stripe-element');
    payButton.disabled = false;
  } catch (error) {
    showError(error);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!checkout) return;
  payButton.disabled = true;
  showMessage('Payment is being processed...');
  try {
    if (checkout.provider === 'stripe') {
      if (!elements) throw new Error('Stripe payment form is not ready.');
      const submitted = await elements.submit();
      if (submitted.error) throw new Error(submitted.error.message);
      const confirmed = await stripe.confirmPayment({
        elements, clientSecret,
        confirmParams: {return_url: location.origin + '/receipt?id=' + paymentId},
        redirect: 'if_required'
      });
      if (confirmed.error) throw new Error(confirmed.error.message);
      location.href = '/receipt?id=' + encodeURIComponent(paymentId);
      return;
    }

    const card = document.getElementById('card-number').value.replace(/\s/g, '');
    const expiry = document.getElementById('expiry').value;
    const cvc = document.getElementById('cvc').value;
    if (!/^\d{16}$/.test(card)) throw new Error('Enter a 16-digit demo card, for example 4242 4242 4242 4242.');
    if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(expiry)) throw new Error('Enter expiry as MM/YY, for example 12/34.');
    if (!/^\d{3,4}$/.test(cvc)) throw new Error('Enter a 3 or 4 digit CVC.');

    const response = await fetch('/payments', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Idempotency-Key': 'ui-' + crypto.randomUUID()},
      body: JSON.stringify({...checkout, demoCardNumber: card})
    });
    const payment = await response.json();
    if (!response.ok || !payment.id) throw new Error(payment.message || 'Payment could not be processed');
    location.href = '/receipt?id=' + encodeURIComponent(payment.id);
  } catch (error) {
    showError(error);
  }
});
</script>
</body>
</html>`;

