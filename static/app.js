const $ = (selector) => document.querySelector(selector);
const connection = $("#connection");
const history = { cpu: [], ram: [], temp: [], down: [], up: [] };
let dialogAction = null;

function bytes(value, rate = false) {
  if (value == null) return "Unavailable";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = Number(value), unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size.toFixed(unit >= 3 ? 1 : 0)} ${units[unit]}${rate ? "/s" : ""}`;
}
function duration(seconds) {
  seconds = Math.max(0, Number(seconds || 0));
  const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600), m = Math.floor(seconds % 3600 / 60);
  return [d && `${d}d`, h && `${h}h`, `${m}m`].filter(Boolean).join(" ");
}
function safe(value) { const node = document.createElement("span"); node.textContent = String(value ?? "Unavailable"); return node.innerHTML; }
function setText(selector, value) { const node = $(selector); if (node) node.textContent = value; }
function setBar(selector, value) { const node = $(selector); if (node) node.style.width = `${Math.max(0, Math.min(100, Number(value || 0)))}%`; }
async function api(path, options) {
  const response = await fetch(path, { ...options, headers: { Accept: "application/json" } });
  const body = await response.json().catch(() => ({ error: "Invalid server response" }));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}
function pushHistory(key, value) { history[key].push(Number(value || 0)); if (history[key].length > 75) history[key].shift(); }
function drawChart(id, values, color, maxValue = null, secondValues = null) {
  const canvas = $(`#${id}`), rect = canvas.getBoundingClientRect(), scale = window.devicePixelRatio || 1;
  if (!rect.width || !rect.height) return;
  canvas.width = rect.width * scale; canvas.height = rect.height * scale;
  const ctx = canvas.getContext("2d"); ctx.scale(scale, scale); ctx.clearRect(0, 0, rect.width, rect.height);
  const all = secondValues ? values.concat(secondValues) : values;
  const ceiling = maxValue || Math.max(...all, 1) * 1.15;
  ctx.strokeStyle = "#263348"; ctx.lineWidth = 1;
  for (let y = 1; y < 4; y += 1) { ctx.beginPath(); ctx.moveTo(0, rect.height * y / 4); ctx.lineTo(rect.width, rect.height * y / 4); ctx.stroke(); }
  const plot = (data, stroke) => {
    if (data.length < 2) return; ctx.beginPath(); ctx.strokeStyle = stroke; ctx.lineWidth = 1.7;
    data.forEach((value, index) => { const x = index * rect.width / 74, y = rect.height - Math.min(value / ceiling, 1) * (rect.height - 3); index ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
  };
  plot(values, color); if (secondValues) plot(secondValues, "#9b7cff");
}

function renderSystem(data) {
  setText("#model", data.model); setText("#os", data.os); setText("#kernel", `Linux ${data.kernel}`); setText("#architecture", data.architecture);
  setText("#uptime", duration(data.uptime_seconds)); setText("#boot-time", new Date(data.boot_time * 1000).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})); setText("#process-count", data.process_count);
  const health = $("#health-state"); health.classList.toggle("warning", data.health.status !== "good"); health.querySelector("strong").textContent = data.health.status === "good" ? "All systems operational" : "Attention needed";
  const checks = data.health.warnings.length ? data.health.warnings : [data.throttling.available ? "No throttling or undervoltage" : "Firmware health unavailable", "Temperature normal", "Storage healthy"];
  $("#health-details").innerHTML = checks.map(item => `<span>${safe(item)}</span>`).join("");
  setText("#cpu-total", `${data.cpu_percent.toFixed(1)}%`); setBar("#cpu-bar", data.cpu_percent);
  $("#cores").innerHTML = data.cpu_per_core.map((value, index) => `<div class="core"><span>Core ${index}</span><div class="mini-bar"><i style="width:${Math.min(value,100)}%"></i></div><b>${value.toFixed(0)}%</b></div>`).join("");
  setText("#clock", data.cpu_frequency_mhz ? `${(data.cpu_frequency_mhz / 1000).toFixed(2)} GHz` : "Unavailable"); setText("#temperature", data.temperature_c == null ? "Unavailable" : `${data.temperature_c.toFixed(1)} C`); setText("#load", data.load_average ? data.load_average.map(v => v.toFixed(2)).join(" / ") : "Unavailable");
  setText("#ram-total", `${bytes(data.memory.used)} / ${bytes(data.memory.total)}`); setBar("#ram-bar", data.memory.percent); setText("#ram-available", bytes(data.memory.available)); setText("#ram-cached", bytes(data.memory.cached)); setText("#ram-free", bytes(data.memory.free)); setText("#swap", `${bytes(data.swap.used)} / ${bytes(data.swap.total)}`);
  $("#process-list").innerHTML = data.top_processes.map(p => `<div class="table-row"><span>${safe(p.name)} <small>${p.pid}</small></span><span>${p.cpu_percent.toFixed(1)}%</span><span>${bytes(p.memory_bytes)}</span></div>`).join("");
  pushHistory("cpu", data.cpu_percent); pushHistory("ram", data.memory.percent); pushHistory("temp", data.temperature_c);
  drawChart("cpu-chart", history.cpu, "#68a4ff", 100); drawChart("ram-chart", history.ram, "#3ed598", 100); drawChart("temp-chart", history.temp, "#f0bd55", 90);
}

function renderStorage(data) {
  setText("#storage-percent", `${data.percent.toFixed(1)}%`); setBar("#storage-bar", data.percent); setText("#storage-used", `${bytes(data.used)} used`); setText("#storage-free", `${bytes(data.free)} free`);
  const warning = $("#storage-warning"); warning.hidden = !data.warning; warning.textContent = data.warning || "";
  setText("#storage-page-percent", `${data.percent.toFixed(1)}%`); setText("#storage-page-free", bytes(data.free)); setBar("#storage-page-bar", data.percent);
  $("#storage-facts").innerHTML = [["Used",bytes(data.used)],["Total",bytes(data.total)],["Filesystem",data.filesystem],["Mount",data.mountpoint],["Device",data.device]].map(([a,b]) => `<span>${a}<strong>${safe(b)}</strong></span>`).join("");
  setText("#disk-read", bytes(data.read_bps, true)); setText("#disk-write", bytes(data.write_bps, true));
  $("#disk-totals").innerHTML = `<span>Read since boot <strong>${bytes(data.read_bytes_since_boot)}</strong></span><span>Written since boot <strong>${bytes(data.write_bytes_since_boot)}</strong></span>`;
}
function interfaceHtml(label, data, traffic) {
  const state = data.connected ? "Connected" : (data.available ? "Disconnected" : "Unavailable");
  const io = traffic.interfaces[data.interface] || {};
  return `<div class="interface-status"><i class="dot ${data.connected ? "on" : ""}"></i><strong>${state}</strong></div><div class="detail-list"><span>IPv4 <strong>${safe(data.ipv4)}</strong></span><span>Interface <strong>${safe(data.interface)}</strong></span><span>MAC <strong>${safe(data.mac)}</strong></span><span>Speed <strong>${data.speed_mbps ? `${data.speed_mbps} Mbps` : "Unavailable"}</strong></span>${label === "wifi" ? `<span>Signal <strong>${data.wifi_signal_dbm == null ? "Unavailable" : `${data.wifi_signal_dbm} dBm`}</strong></span>` : ""}<span>Download <strong>${bytes(io.download_bps || 0,true)}</strong></span><span>Upload <strong>${bytes(io.upload_bps || 0,true)}</strong></span><span>Received <strong>${bytes(io.bytes_received || 0)}</strong></span><span>Sent <strong>${bytes(io.bytes_sent || 0)}</strong></span></div>`;
}
function renderNetwork(data) {
  $("#ethernet-detail").innerHTML = interfaceHtml("ethernet", data.ethernet, data.traffic); $("#wifi-detail").innerHTML = interfaceHtml("wifi", data.wifi, data.traffic);
  const ts = data.tailscale; $("#tailscale-detail").innerHTML = `<div class="interface-status"><i class="dot ${ts.connected ? "on" : ""}"></i><strong>${ts.connected ? "Connected" : "Disconnected"}</strong></div><div class="detail-list"><span>IPv4 <strong>${safe(ts.ipv4)}</strong></span><span>Exit node <strong>${ts.exit_node_advertising ? "Advertising" : "Off"}</strong></span><span>Peers online <strong>${ts.online_peers ?? 0}</strong></span></div><div class="peer-list">${(ts.peers || []).map(p => `<div class="peer"><span>${safe(p.name)}</span><span>${p.online ? "Online" : "Offline"}</span></div>`).join("")}</div>`;
  $("#routing-detail").innerHTML = `<div class="detail-list"><span>Default gateway <strong>${safe(data.default_gateway)}</strong></span><span>DNS servers <strong>${safe(data.dns_servers.join(", ") || "Unavailable")}</strong></span></div>`;
  const names = [data.ethernet.interface,data.wifi.interface].filter(Boolean), totals = names.reduce((a,n) => { const io=data.traffic.interfaces[n]||{}; a.down+=(io.download_bps||0);a.up+=(io.upload_bps||0);return a;},{down:0,up:0});
  setText("#download-rate", bytes(totals.down,true)); setText("#upload-rate", bytes(totals.up,true)); pushHistory("down", totals.down); pushHistory("up", totals.up); drawChart("network-chart",history.down,"#3ed598",null,history.up);
}
function renderServices(data) {
  $("#service-cards").innerHTML = data.services.map(service => `<article class="panel service-card"><div class="service-top"><h2><i class="dot ${service.state === "running" ? "on" : ""}"></i>${safe(service.label)}</h2><span class="status ${service.state}">${service.state}</span></div><div class="service-stats"><div><span>UPTIME</span><strong>${service.started_at ? duration(Date.now()/1000-service.started_at) : "--"}</strong></div><div><span>PID</span><strong>${service.pid || "--"}</strong></div><div><span>RESTARTS</span><strong>${service.restart_count ?? "--"}</strong></div><div><span>CPU</span><strong>${service.cpu_percent == null ? "--" : `${service.cpu_percent.toFixed(1)}%`}</strong></div><div><span>MEMORY</span><strong>${bytes(service.memory_bytes)}</strong></div><div><span>UNIT</span><strong>${safe(service.unit)}</strong></div></div><div class="service-url">${safe(service.url || "System service")}</div>${["aryehlab","printer-camera"].includes(service.id) ? `<div class="service-actions"><button class="button" data-restart="${service.id}">Restart</button></div>` : ""}</article>`).join("");
  document.querySelectorAll("[data-restart]").forEach(button => button.addEventListener("click", () => restart(button)));
}
async function refresh() {
  try {
    const [system,network,services,storage] = await Promise.all([api("/api/system"),api("/api/network"),api("/api/services"),api("/api/storage")]);
    renderSystem(system);renderNetwork(network);renderServices(services);renderStorage(storage);
    connection.textContent=`Online · ${new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}`;connection.classList.add("online");
  } catch(error){connection.textContent="Dashboard unavailable";connection.classList.remove("online");showError(error.message);}
}
async function restart(button){button.disabled=true;button.textContent="Restarting...";try{await api(`/api/services/${button.dataset.restart}/restart`,{method:"POST"});setTimeout(refresh,1500)}catch(error){showError(error.message)}finally{button.disabled=false;button.textContent="Restart"}}
function showError(message){const toast=$("#toast");toast.textContent=message;toast.hidden=false;clearTimeout(showError.timer);showError.timer=setTimeout(()=>toast.hidden=true,4500)}
document.querySelectorAll("[data-page]").forEach(button=>button.addEventListener("click",()=>{const page=button.dataset.page;document.querySelectorAll(".page").forEach(node=>node.classList.toggle("active",node.id===`page-${page}`));document.querySelectorAll(".nav-item").forEach(node=>node.classList.toggle("active",node.dataset.page===page));setText("#page-title",page[0].toUpperCase()+page.slice(1));setTimeout(()=>{drawChart("cpu-chart",history.cpu,"#68a4ff",100);drawChart("ram-chart",history.ram,"#3ed598",100);drawChart("temp-chart",history.temp,"#f0bd55",90);drawChart("network-chart",history.down,"#3ed598",null,history.up)},0)}));
function showDialog(action){dialogAction=action;const shutdown=action==="shutdown";setText("#dialog-title",shutdown?"Shut down PI-4?":"Reboot PI-4?");setText("#dialog-copy",shutdown?"All running services will stop and the Pi will safely unmount the SD card.":"The dashboard and all services will be briefly unavailable while the Pi restarts.");setText("#confirm",shutdown?"Shut Down":"Reboot");$("#modal").hidden=false}
$("#shutdown").addEventListener("click",()=>showDialog("shutdown"));$("#reboot").addEventListener("click",()=>showDialog("reboot"));$("#cancel").addEventListener("click",()=>$("#modal").hidden=true);
$("#confirm").addEventListener("click",async()=>{const action=dialogAction;$("#confirm").disabled=true;try{await api(`/api/system/${action}`,{method:"POST"});$("#modal").hidden=true;setText("#takeover-title",action==="shutdown"?"PI-4 is shutting down":"PI-4 is rebooting");setText("#takeover-copy",action==="shutdown"?"Wait until activity has stopped before removing power.":"Please wait. The dashboard will return when startup is complete.");$("#takeover").hidden=false}catch(error){showError(error.message)}finally{$("#confirm").disabled=false}});
window.addEventListener("resize",()=>{drawChart("cpu-chart",history.cpu,"#68a4ff",100);drawChart("ram-chart",history.ram,"#3ed598",100);drawChart("temp-chart",history.temp,"#f0bd55",90);drawChart("network-chart",history.down,"#3ed598",null,history.up)});
refresh();setInterval(refresh,4000);
