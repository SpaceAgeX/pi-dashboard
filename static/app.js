const $ = (selector) => document.querySelector(selector);
const connection = $("#connection");
const toast = $("#toast");
let dialogAction = null;

function bytes(value) {
  if (value == null) return "Unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size.toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`;
}
function uptime(seconds) {
  const days = Math.floor(seconds / 86400), hours = Math.floor((seconds % 86400) / 3600), mins = Math.floor((seconds % 3600) / 60);
  return [days && `${days}d`, hours && `${hours}h`, `${mins}m`].filter(Boolean).join(" ");
}
function escapeHtml(value) { const div = document.createElement("div"); div.textContent = String(value); return div.innerHTML; }
async function api(path, options) {
  const response = await fetch(path, { ...options, headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => ({ error: "Invalid server response" }));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}
function metric(label, value) { return `<div class="metric"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`; }
function interfaceRow(label, data) {
  const state = data.connected ? "connected" : (data.available ? "stopped" : "unavailable");
  return `<div class="row"><div class="row-main"><strong>${label}</strong><small>${escapeHtml(data.interface || "No interface")} · ${escapeHtml(data.ipv4 || "No IPv4 address")}</small></div><span class="status ${state}">${data.connected ? "connected" : (data.available ? "disconnected" : "unavailable")}</span></div>`;
}
async function refresh() {
  try {
    const [system, network, services] = await Promise.all([api("/api/system"), api("/api/network"), api("/api/services")]);
    $("#system-grid").classList.remove("loading");
    $("#system-grid").innerHTML = metric("Hostname", system.hostname) + metric("CPU", `${system.cpu_percent.toFixed(1)}%`) + metric("Temperature", system.temperature_c == null ? "Unavailable" : `${system.temperature_c} °C`) + metric("Memory", `${bytes(system.memory.used)} / ${bytes(system.memory.total)}`) + metric("Disk", `${bytes(system.disk.used)} / ${bytes(system.disk.total)} · ${bytes(system.disk.free)} free`) + metric("Uptime", uptime(system.uptime_seconds));
    $("#network-list").classList.remove("loading");
    $("#network-list").innerHTML = interfaceRow("Ethernet", network.ethernet) + interfaceRow("Wi-Fi", network.wifi) + interfaceRow("Tailscale", network.tailscale);
    $("#service-list").classList.remove("loading");
    $("#service-list").innerHTML = services.services.map(service => `<div class="row"><div class="row-main"><strong>${escapeHtml(service.label)}</strong><small>${escapeHtml(service.unit)}</small></div><span class="status ${service.state}">${service.state}</span>${["aryehlab", "printer-camera"].includes(service.id) ? `<button class="button small" data-restart="${service.id}">Restart</button>` : ""}</div>`).join("");
    document.querySelectorAll("[data-restart]").forEach(button => button.addEventListener("click", () => restart(button)));
    connection.textContent = `Online · updated ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}`;
    connection.classList.add("online");
  } catch (error) { connection.textContent = "Dashboard unavailable"; connection.classList.remove("online"); showError(error.message); }
}
async function restart(button) {
  button.disabled = true; button.textContent = "Restarting…";
  try { await api(`/api/services/${button.dataset.restart}/restart`, { method: "POST" }); setTimeout(refresh, 1500); }
  catch (error) { showError(error.message); }
  finally { button.disabled = false; button.textContent = "Restart"; }
}
function showError(message) { toast.textContent = message; toast.hidden = false; clearTimeout(showError.timer); showError.timer = setTimeout(() => toast.hidden = true, 4500); }
function showDialog(action) {
  dialogAction = action;
  const shutdown = action === "shutdown";
  $("#dialog-title").textContent = shutdown ? "Shut down PI-4?" : "Reboot PI-4?";
  $("#dialog-copy").textContent = shutdown ? "All running services will stop and the Pi will safely unmount the SD card." : "The dashboard and all services will be briefly unavailable while the Pi restarts.";
  $("#confirm").textContent = shutdown ? "Shut Down" : "Reboot";
  $("#modal").hidden = false;
}
$("#shutdown").addEventListener("click", () => showDialog("shutdown"));
$("#reboot").addEventListener("click", () => showDialog("reboot"));
$("#cancel").addEventListener("click", () => $("#modal").hidden = true);
$("#confirm").addEventListener("click", async () => {
  const action = dialogAction; $("#confirm").disabled = true;
  try {
    await api(`/api/system/${action}`, { method: "POST" });
    $("#modal").hidden = true; $("#takeover-title").textContent = action === "shutdown" ? "PI-4 is shutting down" : "PI-4 is rebooting";
    $("#takeover-copy").textContent = action === "shutdown" ? "Wait until activity has stopped before removing power." : "Please wait. The dashboard will return when startup is complete.";
    $("#takeover").hidden = false;
  } catch (error) { showError(error.message); }
  finally { $("#confirm").disabled = false; }
});
refresh(); setInterval(refresh, 4000);

