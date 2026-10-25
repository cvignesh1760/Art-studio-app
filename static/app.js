// Small helpers shared by all pages.

// Talk to the backend. Throws an Error (with .status) when something goes wrong.
async function api(path, method, body) {
  let response;
  try {
    response = await fetch("/api" + path, {
      method: method || "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new Error("Could not reach the server. Is it running?");
  }
  let data = null;
  try { data = await response.json(); } catch (e) { /* no body */ }
  if (!response.ok) {
    const err = new Error((data && data.error) || "Something went wrong.");
    err.status = response.status;
    throw err;
  }
  return data;
}

// Escape text before putting it into HTML (stops people injecting HTML/scripts).
function esc(value) {
  return String(value).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function money(n) {
  return "₹" + Number(n).toLocaleString("en-IN");
}

// Show a message as a small pop-up at the bottom of the screen.
// (the page needs an empty <div id="message"></div>)
let toastTimer = null;
function showMessage(id, text, isError) {
  const box = document.getElementById(id);
  box.className = "toast " + (isError ? "error" : "success");
  box.setAttribute("role", "status");
  box.textContent = text;
  // wait one tick so the fade-in animation plays
  setTimeout(function () { box.classList.add("show"); }, 10);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { box.classList.remove("show"); }, isError ? 6000 : 4000);
}

// Loading -> empty / error / data. Used by every screen that loads a list.
async function loadList(boxId, fetcher, render, emptyText) {
  const box = document.getElementById(boxId);
  box.innerHTML = '<p class="loading">Loading...</p>';
  try {
    const items = await fetcher();
    box.innerHTML = items.length ? render(items) : '<p class="empty">' + esc(emptyText) + "</p>";
  } catch (e) {
    box.innerHTML = '<p class="error">' + esc(e.message) + "</p>";
  }
}

// ---------- Painting pictures ----------
// The image file lives in static/images and its path is saved in the database (image_url).
function paintingImage(p) {
  if (!p.image_url) return '<span class="noimg">Image coming soon</span>';
  return '<img src="/' + esc(p.image_url) + '" alt="' + esc(p.title) + '" loading="lazy" onerror="imageFailed(this)">';
}

// If the file is missing, show the "coming soon" box instead of a broken image icon.
function imageFailed(img) {
  const box = img.parentNode;
  img.remove();
  box.insertAdjacentHTML("beforeend", '<span class="noimg">Image coming soon</span>');
}

// ---------- Warli-style dancers (drawn with code so no image file is needed) ----------
function dancersSvg() {
  const figure =
    '<circle cy="-27" r="4.5"/>' +
    '<path d="M-7 -21 L7 -21 L0 -5 Z"/>' +
    '<path d="M0 -5 L-7 11 L7 11 Z"/>' +
    '<path d="M-6 -17 L-27 -10 M6 -17 L27 -10 M-3 11 L-9 25 M3 11 L9 25" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>';
  const count = 14, radius = 120;
  let ring = "";
  for (let i = 0; i < count; i++) {
    ring += '<g transform="rotate(' + (i * 360 / count) + ') translate(0,-' + radius + ')">' + figure + "</g>";
  }
  let rays = "";
  for (let i = 0; i < 12; i++) {
    rays += '<line x1="0" y1="-42" x2="0" y2="-54" transform="rotate(' + (i * 30) + ')"/>';
  }
  return '<svg viewBox="-200 -200 400 400" aria-hidden="true">' +
    '<circle r="74" fill="none" stroke="#fff" stroke-opacity=".3" stroke-dasharray="3 7"/>' +
    '<g class="ring" fill="#fff">' + ring + "</g>" +
    '<circle r="32" fill="#E9A820"/>' +
    '<g stroke="#E9A820" stroke-width="4" stroke-linecap="round">' + rays + "</g></svg>";
}

// Small logo for the top bar
const LOGO = '<svg viewBox="-20 -34 40 66" fill="#E9A820" aria-hidden="true"><circle cy="-27" r="5"/><path d="M-8 -20 L8 -20 L0 -3 Z"/><path d="M0 -3 L-8 14 L8 14 Z"/><path d="M-4 14 L-10 30 M4 14 L10 30" stroke="#E9A820" stroke-width="3" stroke-linecap="round" fill="none"/></svg>';

// Make sure someone is logged in; otherwise go to the login page.
async function requireLogin(allowedRole) {
  let user;
  try {
    user = await api("/me");
  } catch (e) {
    if (e.status === 401) { window.location.href = "login.html"; return null; }
    document.body.innerHTML = '<p class="error">' + esc(e.message) + "</p>";
    return null;
  }
  if (allowedRole && user.role !== allowedRole) {
    document.body.innerHTML = '<div class="page"><p class="error">You are not allowed to see this page.</p><p><a href="index.html">Back to the paintings</a></p></div>';
    return null;
  }
  drawNav(user);
  return user;
}

function drawNav(user) {
  const here = window.location.pathname.split("/").pop() || "index.html";
  const items = [["index.html", "Paintings"]];
  if (user.role === "customer") {
    items.push(["book.html", "Book a wall"], ["pottery.html", "Request pottery"]);
  }
  items.push(["dashboard.html", user.role === "admin" ? "All requests" : "My orders"]);
  if (user.role === "admin") items.push(["admin-paintings.html", "Manage paintings"]);

  const links = items.map(function (item) {
    return '<a href="' + item[0] + '"' + (item[0] === here ? ' class="active"' : "") + ">" + item[1] + "</a>";
  }).join("");

  document.getElementById("nav").innerHTML =
    '<div class="bar"><a class="brand" href="index.html">' + LOGO + "Art Studio</a>" +
    '<nav class="links">' + links + "</nav>" +
    '<div class="who">' + esc(user.name) + " (" + user.role + ') <a href="#" id="logout">Log out</a></div></div>';

  document.getElementById("logout").onclick = async function (e) {
    e.preventDefault();
    await api("/logout", "POST");
    window.location.href = "login.html";
  };
}
