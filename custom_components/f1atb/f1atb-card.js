/**
 * Carte Lovelace interactive pour l'intégration F1ATB Solar Router.
 * Auto-détecte les entités de l'intégration (aucune config requise), et pilote
 * par action active : forme d'onde, ouverture max, forçage (Auto/Marche/Arrêt).
 *
 * Installation : copier ce fichier dans <config>/www/ puis ajouter une ressource
 *   URL: /local/f1atb-card.js   Type: JavaScript Module
 * Puis dans une vue : ajouter une carte « Manuel » avec  type: custom:f1atb-card
 */
const F1ATB_CARD_VERSION = "0.4.5";

const LOGO = `
<svg viewBox="44 60 186 128" class="logo">
 <rect x="118" y="96" width="72" height="86" rx="14" fill="#54565c" stroke="#2f3036" stroke-width="3.5"/>
 <g stroke="#eef0f2" stroke-width="2.8" stroke-linecap="round" fill="none">
  <path d="M154,116 L154,132"/><path d="M135,133 L173,133"/><path d="M135,133 L135,151"/><path d="M154,133 L154,153"/><path d="M173,133 L173,151"/></g>
 <circle cx="154" cy="115" r="5" fill="#eef0f2"/><circle cx="154" cy="133" r="3.6" fill="#eef0f2"/>
 <circle cx="135" cy="155" r="4.6" fill="#eef0f2"/><circle cx="154" cy="157" r="4.6" fill="#eef0f2"/><circle cx="173" cy="155" r="4.6" fill="#eef0f2"/>
 <text x="154" y="177" fill="#e6e7ea" font-family="Arial" font-weight="700" font-size="14" text-anchor="middle">F1ATB</text>
 <g stroke="#17181c" stroke-width="5.5" stroke-linecap="round"><path d="M192,120 L214,120"/><path d="M192,139 L214,139"/><path d="M192,158 L214,158"/></g>
 <polygon points="224,120 213,113.5 213,126.5" fill="#17181c"/><polygon points="224,139 213,132.5 213,145.5" fill="#17181c"/><polygon points="224,158 213,151.5 213,164.5" fill="#17181c"/>
 <path d="M100,120 C100,142 106,150 118,150" fill="none" stroke="#17181c" stroke-width="8" stroke-linecap="round"/>
 <polygon points="70,66 160,88 138,128 48,106" fill="#17181c"/><polygon points="72.1,67.9 156.6,88.5 135.9,126.1 51.4,105.5" fill="#ffffff"/>
 <polygon points="75.1,71.6 97.3,77 89.3,91.6 67.1,86.2" fill="#3f4149"/><polygon points="101.8,78.1 124,83.5 116,98.1 93.8,92.7" fill="#3f4149"/><polygon points="128.5,84.6 150.7,90 142.7,104.6 120.5,99.2" fill="#3f4149"/>
 <polygon points="65.3,89.4 87.5,94.8 79.5,109.4 57.3,104" fill="#3f4149"/><polygon points="92,95.9 114.2,101.3 106.2,115.9 84,110.5" fill="#3f4149"/><polygon points="118.7,102.4 140.9,107.8 132.9,122.4 110.7,117" fill="#3f4149"/>
</svg>`;

const STYLE = `
:host{
 /* Couleurs sémantiques (fixes, elles portent un sens) */
 --imp:#f0663d;--exp:#12b981;--triac:#2f7ff0;--relais:#0ea5a5;
 /* Surfaces / texte / traits : suivent le thème HA (dark<->light auto) */
 --ink:var(--primary-text-color,#141821);
 --ink2:var(--secondary-text-color,#565c6a);
 --muted:var(--secondary-text-color,#8a909c);
 --line:var(--divider-color,#e6e8ee);
 --surf:var(--ha-card-background,var(--card-background-color,#fff));
 --plane:var(--secondary-background-color,#f4f6f9);
}
.wrap{background:var(--surf);border-radius:16px;overflow:hidden;font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif);color:var(--ink)}
.head{display:flex;align-items:center;gap:12px;padding:14px 18px}
.logo{height:44px;width:auto;flex:0 0 auto}
.title{font-size:17px;font-weight:700}
.sub{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--muted);flex:none}
.dot.on{background:var(--exp)}.dot.off{background:var(--imp)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;padding:0 18px 14px}
.kpi{background:var(--plane);border:1px solid var(--line);border-radius:12px;padding:11px 13px}
.kpi .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);font-weight:600;display:flex;align-items:center;gap:6px}
.kpi .v{font-size:22px;font-weight:680;letter-spacing:-.5px;margin-top:5px;line-height:1}
.kpi .v small{font-size:12px;font-weight:500;color:var(--ink2)}
.tag{width:8px;height:8px;border-radius:3px;display:inline-block}
.temps{display:flex;flex-wrap:wrap;gap:8px;padding:0 18px 14px;margin-top:-4px}
.tchip{display:flex;align-items:center;gap:6px;background:var(--plane);border:1px solid var(--line);border-radius:20px;padding:6px 12px;font-size:12.5px}
.tchip .tn{color:var(--ink2);font-weight:600}
.tchip .tv{color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
.act{margin:0 14px 14px;border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:var(--surf)}
.act .top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.act .nm{font-size:15px;font-weight:650}
.act .ouv{font-size:15px;font-weight:700;color:var(--triac)}
.bar{height:8px;border-radius:5px;background:var(--line);overflow:hidden;margin-bottom:14px}
.bar i{display:block;height:100%;border-radius:5px;background:var(--triac);transition:width .4s}
.row{margin-bottom:12px}
.row>.lab{font-size:11.5px;color:var(--ink2);font-weight:600;margin-bottom:6px;display:flex;justify-content:space-between}
.seg{display:flex;flex-wrap:wrap;gap:6px}
.seg button{flex:1 1 auto;min-width:64px;border:1px solid var(--line);background:var(--plane);color:var(--ink2);border-radius:9px;padding:8px 10px;font-size:12.5px;font-weight:600;cursor:pointer;transition:all .12s}
.seg button:hover{border-color:var(--primary-color,var(--triac))}
.seg button.on{background:var(--triac);border-color:var(--triac);color:#fff;box-shadow:0 2px 7px rgba(47,127,240,.3)}
.forc button.on.marche{background:var(--exp);border-color:var(--exp);box-shadow:0 2px 7px rgba(18,185,129,.3)}
.forc button.on.arret{background:var(--imp);border-color:var(--imp);box-shadow:0 2px 7px rgba(240,102,61,.3)}
.slider{display:flex;align-items:center;gap:10px}
.slider input[type=range]{flex:1;accent-color:var(--triac)}
.slider .val{font-size:14px;font-weight:700;min-width:44px;text-align:right}
.hint{color:var(--triac);font-weight:700}
.hint2{color:var(--muted);font-weight:500;font-size:11px}
.pwr{display:flex;align-items:center;gap:9px}
.pwr input[type=number],.pmax input[type=number]{border:1px solid var(--line);border-radius:10px;background:var(--plane);color:var(--ink);font-weight:650;font-variant-numeric:tabular-nums}
.pwr input[type=number]{width:96px;padding:9px 11px;font-size:16px}
.u{color:var(--muted);font-size:13px}
.ghost{margin-left:auto;padding:9px 15px;border:1px solid var(--line);border-radius:10px;background:var(--plane);color:var(--ink2);font-weight:600;cursor:pointer;font-size:13px;transition:all .12s}
.ghost:hover{border-color:var(--primary-color,var(--triac))}
.pmax{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--muted);margin-top:9px;flex-wrap:wrap}
.pmax input[type=number]{width:78px;padding:6px 9px;font-size:12.5px;font-weight:600}
.cal{margin-left:auto;padding:6px 12px;border:1px solid var(--triac);border-radius:9px;background:transparent;color:var(--triac);font-weight:700;font-size:12px;cursor:pointer;transition:all .12s}
.cal:hover{background:var(--triac);color:#fff}
.cal.busy{border-color:var(--muted);color:var(--muted);cursor:progress}
.cal.busy:hover{background:transparent;color:var(--muted)}
.empty{padding:26px;text-align:center;color:var(--muted);font-size:13px}
`;

const FMT = (n, d = 0) => (n == null || isNaN(n)) ? "—" : Number(n).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d });
// Échappement HTML : le nom du routeur/action est du texte libre (firmware) injecté dans innerHTML.
const ESC = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class F1atbCard extends HTMLElement {
  setConfig(config) { this._config = config || {}; }

  set hass(hass) {
    this._hass = hass;
    // Ne pas reconstruire la carte pendant que l'utilisateur saisit dans un champ
    // (sinon le focus et la valeur en cours seraient perdus à chaque mise à jour d'état).
    const ae = this._root && this._root.activeElement;
    if (ae && ae.tagName === "INPUT") return;
    this._render();
  }

  _entities() {
    // Détection robuste : toutes les entités de l'intégration portent l'attribut f1atb_kind.
    const states = this._hass.states || {};
    return Object.keys(states).filter(
      (eid) => states[eid] && states[eid].attributes && states[eid].attributes.f1atb_kind
    );
  }

  _st(eid) { return this._hass.states[eid]; }

  _render() {
    if (!this._hass) return;
    if (!this._root) {
      this._root = this.attachShadow({ mode: "open" });
    }
    // Anti-plantage : ne JAMAIS lever d'erreur (sinon HA affiche « erreur de configuration »),
    // notamment quand le routeur est hors ligne et que les entités sont indisponibles.
    try {
      this._renderInner();
    } catch (e) {
      console.error("f1atb-card:", e);
      this._root.innerHTML =
        '<ha-card><div style="padding:18px;color:var(--secondary-text-color,#888)">Carte F1ATB momentanément indisponible.</div></ha-card>';
    }
  }

  _renderInner() {
    const eids = this._entities();

    // Routeur hors tension / intégration pas encore chargée : AUCUNE entité.
    // On affiche une carte propre au lieu de laisser quoi que ce soit planter.
    if (!eids.length) {
      this._root.innerHTML = `<style>${STYLE}</style>
        <ha-card><div class="wrap">
          <div class="head">${LOGO}<div><div class="title">Routeur F1ATB</div>
            <div class="sub"><span class="dot off"></span>Indisponible</div></div></div>
          <div class="empty">Le routeur ne répond pas (hors tension ?).<br>La carte se remplit dès qu'il est joignable.</div>
        </div></ha-card>`;
      return;
    }

    const globals = {};
    const actions = {}; // index -> {kind: eid}
    let routerName = "Routeur F1ATB";
    for (const eid of eids) {
      const s = this._st(eid);
      if (!s) continue;
      const a = s.attributes || {};
      if (a.action_index !== undefined && a.action_index !== null) {
        const i = a.action_index;
        (actions[i] = actions[i] || { name: a.action_name })[a.f1atb_kind] = eid;
        if (a.action_name) actions[i].name = a.action_name;
      } else if (a.f1atb_kind) {
        globals[a.f1atb_kind] = eid;
      }
    }
    // nom du routeur depuis le device d'une entité (hass.entities/devices peuvent être absents)
    const anyEid = eids[0];
    const ents = this._hass.entities || {};
    const devs = this._hass.devices || {};
    const ent = anyEid ? ents[anyEid] : null;
    const dev = ent && ent.device_id ? devs[ent.device_id] : null;
    if (dev && dev.name_by_user) routerName = dev.name_by_user;
    else if (dev && dev.name) routerName = dev.name;

    // État connecté (capteur binaire "Connecté", f1atb_kind='connected')
    const connEid = globals.connected;
    const online = connEid ? ((this._st(connEid) || {}).state === "on") : true;

    const kpi = (kind, label, tagVar, unit, energy) => {
      const eid = globals[kind];
      const s = eid ? this._st(eid) : null;
      let v = s ? Number(s.state) : null;
      return `<div class="kpi"><div class="l"><span class="tag" style="background:var(${tagVar})"></span>${label}</div>
        <div class="v">${FMT(v, energy ? 1 : 0)}<small>${unit}</small></div></div>`;
    };

    // Températures (canaux configurés) : puces triées par canal
    const tempEids = eids
      .filter((e) => (((this._st(e) || {}).attributes) || {}).f1atb_kind === "temperature")
      .sort((a, b) => (this._st(a).attributes.temp_channel || 0) - (this._st(b).attributes.temp_channel || 0));
    let tempHtml = "";
    if (tempEids.length) {
      tempHtml = `<div class="temps">` + tempEids.map((e) => {
        const s = this._st(e);
        const v = Number(s.state);
        const ch = s.attributes.temp_channel;
        const nm = s.attributes.nom || ("Canal " + (ch === undefined || ch === null ? "?" : ch));
        const disp = (s.state === "unavailable" || s.state === "unknown" || isNaN(v)) ? "—" : FMT(v, 1) + "°C";
        return `<div class="tchip">🌡<span class="tn">${ESC(nm)}</span><span class="tv">${disp}</span></div>`;
      }).join("") + `</div>`;
    }

    const actIdx = Object.keys(actions).map(Number).sort((a, b) => a - b);
    let actionsHtml = "";
    if (actIdx.length === 0) {
      actionsHtml = online
        ? `<div class="empty">Aucune action active.<br>Activez une action sur le routeur pour la piloter ici.</div>`
        : `<div class="empty">Routeur hors ligne.<br>Les commandes réapparaîtront à la remise sous tension.</div>`;
    }
    for (const i of actIdx) {
      const A = actions[i];
      const ouvS = A.ouverture ? this._st(A.ouverture) : null;
      const ouv = ouvS ? Number(ouvS.state) : null;
      const fondeS = A.forme_onde ? this._st(A.forme_onde) : null;
      const omS = A.ouverture_max ? this._st(A.ouverture_max) : null;
      const forcS = A.forcage ? this._st(A.forcage) : null;

      // forme d'onde : segmented
      let ondeHtml = "";
      if (fondeS) {
        const opts = fondeS.attributes.options || [];
        ondeHtml = `<div class="row"><div class="lab"><span>Forme d'onde</span></div><div class="seg" data-role="onde" data-eid="${A.forme_onde}">` +
          opts.map((o) => `<button class="${o === fondeS.state ? "on" : ""}" data-opt="${ESC(o)}">${ESC(o)}</button>`).join("") + `</div></div>`;
      }
      // ouverture max en routage AUTO (triac) : slider
      let autoHtml = "";
      const autoS = A.auto_ouverture_max ? this._st(A.auto_ouverture_max) : null;
      if (autoS) {
        const av = Number(autoS.state);
        autoHtml = `<div class="row"><div class="lab"><span>Ouverture max (Auto)</span><span class="hint2">routage normal</span></div>
          <div class="slider"><input type="range" min="0" max="100" step="1" value="${av}" data-role="om" data-eid="${A.auto_ouverture_max}">
          <span class="val">${FMT(av)}%</span></div></div>`;
      }
      // ouverture appliquée en MARCHE FORCÉE (ForceOuvre) : slider
      let omHtml = "";
      if (omS) {
        const val = Number(omS.state);
        omHtml = `<div class="row"><div class="lab"><span>Ouverture (marche forcée)</span><span class="hint2">si forcé</span></div>
          <div class="slider"><input type="range" min="0" max="100" step="1" value="${val}" data-role="om" data-eid="${A.ouverture_max}">
          <span class="val">${FMT(val)}%</span></div></div>`;
      }
      // forçage : Auto / Marche / Arrêt
      let forcHtml = "";
      if (forcS) {
        const cur = forcS.state;
        // data-opt = la VRAIE option de l'entité (ex. "Forcé Marche") ; on n'affiche qu'un libellé lisible.
        const FORC_LABEL = { "Auto": "Auto", "Forcé Marche": "Marche forcée", "Forcé Arrêt": "Arrêt forcé" };
        const FORC_CLS = { "Forcé Marche": "marche", "Forcé Arrêt": "arret" };
        const opts = forcS.attributes.options || ["Auto", "Forcé Marche", "Forcé Arrêt"];
        forcHtml = `<div class="row"><div class="lab"><span>Forçage</span></div><div class="seg forc" data-role="forc" data-eid="${A.forcage}">` +
          opts.map((v) => `<button class="${cur === v ? "on " + (FORC_CLS[v] || "") : ""}" data-opt="${ESC(v)}">${ESC(FORC_LABEL[v] || v)}</button>`).join("") + `</div></div>`;
      }

      // marche forcée à une puissance donnée (l'ouverture est calculée automatiquement)
      let mfHtml = "";
      const mfS = A.marche_forcee_w ? this._st(A.marche_forcee_w) : null;
      if (mfS) {
        const pmaxS = A.puissance_max ? this._st(A.puissance_max) : null;
        const pmax = (pmaxS ? Number(pmaxS.state) : Number(mfS.attributes.puissance_max)) || 3000;
        const calibrating = !!(pmaxS && pmaxS.attributes && pmaxS.attributes.calibrating);
        const mfVal = Number(mfS.state) || 0;
        const op = pmax ? Math.max(0, Math.min(100, Math.round(mfVal / pmax * 100))) : 0;
        const calBtn = A.calibrer
          ? `<button class="cal ${calibrating ? "busy" : ""}" data-role="cal" data-eid="${A.calibrer}" ${calibrating ? "disabled" : ""}>${calibrating ? "Calibration…" : "⚙ Calibrer"}</button>`
          : ``;
        mfHtml = `<div class="row"><div class="lab"><span>Marche forcée à une puissance</span><span class="hint" data-role="mfpct">→ ${op} %</span></div>
          <div class="pwr">
            <input type="number" inputmode="numeric" min="0" max="${pmax}" step="50" value="${mfVal}" data-role="mfw" data-eid="${A.marche_forcee_w}" data-pmax="${pmax}"><span class="u">W</span>
            <button class="ghost" data-role="mfauto" data-eid="${A.marche_forcee_w}" title="Remettre à 0 (retour Auto)">Effacer</button>
          </div>`
          + (A.puissance_max ? `<div class="pmax">Puissance max de l'appareil <input type="number" inputmode="numeric" min="0" step="50" value="${pmax}" data-role="pmax" data-eid="${A.puissance_max}"><span class="u">W</span>${calBtn}</div>` : ``)
          + `</div>`;
      }

      actionsHtml += `<div class="act">
        <div class="top"><div class="nm">${ESC(A.name || "Action " + i)}</div><div class="ouv">${ouv == null ? "" : FMT(ouv) + " %"}</div></div>
        <div class="bar"><i style="width:${Math.max(0, Math.min(100, ouv || 0))}%"></i></div>
        ${ondeHtml}${autoHtml}${forcHtml}${omHtml}${mfHtml}
      </div>`;
    }

    this._root.innerHTML = `<style>${STYLE}</style>
      <ha-card><div class="wrap">
        <div class="head">${LOGO}<div><div class="title">${ESC(routerName)}</div>
          <div class="sub"><span class="dot ${online ? "on" : "off"}"></span>${online ? "En ligne" : "Hors ligne"}</div></div></div>
        <div class="kpis">
          ${kpi("grid_import_power", "Soutirée", "--imp", "W", false)}
          ${kpi("grid_export_power", "Injectée", "--exp", "W", false)}
          ${kpi("routed_power", "Routée", "--triac", "W", false)}
        </div>
        ${tempHtml}
        ${actionsHtml}
      </div></ha-card>`;

    this._bind();
  }

  _bind() {
    // Selects segmentés (forme d'onde + forçage)
    this._root.querySelectorAll('.seg').forEach((seg) => {
      const eid = seg.getAttribute("data-eid");
      seg.querySelectorAll("button").forEach((b) => {
        b.onclick = () => {
          this._hass.callService("select", "select_option", { entity_id: eid, option: b.getAttribute("data-opt") });
        };
      });
    });
    // Sliders ouverture max
    this._root.querySelectorAll('input[data-role="om"]').forEach((sl) => {
      const eid = sl.getAttribute("data-eid");
      const val = sl.parentElement.querySelector(".val");
      sl.oninput = () => { if (val) val.textContent = sl.value + "%"; };
      sl.onchange = () => {
        this._hass.callService("number", "set_value", { entity_id: eid, value: Number(sl.value) });
      };
    });
    // Marche forcée (W) : l'ouverture % s'affiche en direct, l'écriture force la marche
    this._root.querySelectorAll('input[data-role="mfw"]').forEach((inp) => {
      const eid = inp.getAttribute("data-eid");
      const pmax = Number(inp.getAttribute("data-pmax")) || 3000;
      const row = inp.closest(".row");
      const pct = row ? row.querySelector('[data-role="mfpct"]') : null;
      inp.oninput = () => {
        const op = pmax ? Math.max(0, Math.min(100, Math.round((Number(inp.value) || 0) / pmax * 100))) : 0;
        if (pct) pct.textContent = "→ " + op + " %";
      };
      inp.onchange = () => {
        const v = Math.min(pmax, Math.max(0, Number(inp.value) || 0));  // borne à la puissance max
        inp.value = v;
        this._hass.callService("number", "set_value", { entity_id: eid, value: v });
      };
    });
    // Bouton Auto : arrête la marche forcée (remet 0)
    this._root.querySelectorAll('button[data-role="mfauto"]').forEach((b) => {
      const eid = b.getAttribute("data-eid");
      b.onclick = () => {
        const row = b.closest(".row");
        const inp = row ? row.querySelector('input[data-role="mfw"]') : null;
        if (inp) inp.value = 0;
        const pct = row ? row.querySelector('[data-role="mfpct"]') : null;
        if (pct) pct.textContent = "→ 0 %";
        this._hass.callService("number", "set_value", { entity_id: eid, value: 0 });
      };
    });
    // Saisie MANUELLE de la puissance max de l'appareil
    this._root.querySelectorAll('input[data-role="pmax"]').forEach((inp) => {
      const eid = inp.getAttribute("data-eid");
      inp.onchange = () => {
        this._hass.callService("number", "set_value", { entity_id: eid, value: Math.max(0, Number(inp.value) || 0) });
      };
    });
    // Bouton Calibrer : lance la mesure auto de la puissance max
    this._root.querySelectorAll('button[data-role="cal"]').forEach((b) => {
      const eid = b.getAttribute("data-eid");
      b.onclick = () => {
        if (b.classList.contains("busy")) return;
        this._hass.callService("button", "press", { entity_id: eid });
      };
    });
  }

  getCardSize() { return 6; }
  static getStubConfig() { return {}; }
}

// Enregistrement IDEMPOTENT. Le fichier peut être chargé DEUX fois : automatiquement par
// l'intégration (add_extra_js_url) ET via une ressource Lovelace ajoutée à la main.
// Sans ce garde, customElements.define() lève « already defined », le module plante et le
// frontend (surtout l'appli mobile) affiche « impossible de charger l'application ».
if (customElements.get("f1atb-card")) {
  // Déjà défini : une AUTRE copie du fichier a été chargée avant (typiquement une vieille
  // ressource Lovelace manuelle `/local/f1atb-card.js` figée, que HACS ne met jamais à jour).
  console.warn(
    `[f1atb-card] v${F1ATB_CARD_VERSION} ignorée : « f1atb-card » est déjà défini par un autre fichier. ` +
    `Supprimez la ressource Lovelace manuelle (Paramètres → Tableaux de bord → Ressources) ` +
    `et le fichier /config/www/f1atb-card.js : l'intégration charge la carte automatiquement.`
  );
} else {
  customElements.define("f1atb-card", F1atbCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c && c.type === "f1atb-card")) {
    window.customCards.push({
      type: "f1atb-card",
      name: "F1ATB Solar Router",
      description: "Carte interactive pour piloter le routeur solaire F1ATB (forme d'onde, ouverture max, forçage, marche forcée à une puissance donnée).",
      preview: true,
    });
  }
  console.info(`%c F1ATB-CARD %c v${F1ATB_CARD_VERSION} `, "background:#2f7ff0;color:#fff;border-radius:4px 0 0 4px;padding:2px 6px", "background:#17181c;color:#fff;border-radius:0 4px 4px 0;padding:2px 6px");
}
