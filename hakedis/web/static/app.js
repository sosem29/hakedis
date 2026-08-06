"use strict";

/* ======================================================================
   hakedis web arayuzu — tek sayfa is mantigi (bagimsiz, yapisiz JS)
   ====================================================================== */

const $ = (sel, kapsam = document) => kapsam.querySelector(sel);
const $$ = (sel, kapsam = document) => [...kapsam.querySelectorAll(sel)];

function esc(m) {
  return String(m ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function derinKopya(o) { return JSON.parse(JSON.stringify(o)); }

function yolAyarla(obje, yol, deger) {
  const parcalar = yol.split(".");
  let d = obje;
  for (let i = 0; i < parcalar.length - 1; i++) {
    if (typeof d[parcalar[i]] !== "object" || d[parcalar[i]] === null) d[parcalar[i]] = {};
    d = d[parcalar[i]];
  }
  d[parcalar[parcalar.length - 1]] = deger;
}

function yolOku(obje, yol, varsayilan) {
  let d = obje;
  for (const p of yol.split(".")) {
    if (d === null || typeof d !== "object" || !(p in d)) return varsayilan;
    d = d[p];
  }
  return d;
}

function sayiFormat(n, basamak) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("tr-TR", {
    minimumFractionDigits: basamak, maximumFractionDigits: basamak,
  });
}

async function api(yol, opts = {}) {
  const yanit = await fetch(yol, opts);
  let veri = null;
  try { veri = await yanit.json(); } catch (_) { /* bos */ }
  if (!yanit.ok) {
    let mesaj = `HTTP ${yanit.status}`;
    if (veri && veri.detail) {
      mesaj = typeof veri.detail === "string" ? veri.detail : JSON.stringify(veri.detail);
    }
    throw new Error(mesaj);
  }
  return veri;
}

function bildirim(mesaj, tur = "ok") {
  const b = $("#bildirim");
  b.textContent = mesaj;
  b.className = "bildirim " + tur;
  b.hidden = false;
  clearTimeout(b._t);
  b._t = setTimeout(() => { b.hidden = true; }, 3400);
}

function indirBlob(blob, dosyaAdi) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = dosyaAdi;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2500);
}
function indirMetin(icerik, dosyaAdi, tur = "text/plain") {
  indirBlob(new Blob([icerik], { type: tur }), dosyaAdi);
}
function indirB64(b64, dosyaAdi, tur) {
  const ikili = atob(b64);
  const bayt = new Uint8Array(ikili.length);
  for (let i = 0; i < ikili.length; i++) bayt[i] = ikili.charCodeAt(i);
  indirBlob(new Blob([bayt], { type: tur }), dosyaAdi);
}

function dosyaAdiTemiz(ad) {
  return (ad || "metraj").replace(/\.[^.]+$/, "") || "metraj";
}

/* ---------------- Sabitler ---------------- */

const TIP_RENKLER = {
  Kolon: "#e74c3c", Perde: "#8e44ad", Kiris: "#2980b9",
  Doseme: "#7f8c8d", Merdiven: "#f39c12", Bosluk: "#95a5a6",
  Kapi: "#16a085", Pencere: "#1abc9c", Bilinmeyen: "#bdc3c7",
};
const TIP_SIRA = ["Kolon", "Perde", "Kiris", "Doseme", "Merdiven", "Bosluk", "Kapi", "Pencere", "Bilinmeyen"];

const ALANLAR = [
  { yol: "birim", etiket: "Birim", tip: "select", secenekler: ["cm", "mm", "m"], panel: "hizli", bolum: "Genel" },
  { yol: "donati.aktif", etiket: "Yaklaşık demir (kg) hesabı", tip: "onay", panel: "hizli", bolum: "Donatı" },
  { yol: "doseme.tip", etiket: "Döşeme tipi", tip: "select", secenekler: ["normal", "guseli", "mantar"], panel: "hizli", bolum: "Döşeme" },
  { yol: "doseme.guseli_hacim_katsayisi", etiket: "Guseli hacim katsayısı", tip: "number", adim: 0.05, panel: "tam", bolum: "Döşeme" },
  { yol: "doseme.mantar_kolon_ustu_artisi", etiket: "Mantar kolon üstü artışı (m)", tip: "number", adim: 0.01, panel: "tam", bolum: "Döşeme" },
  { yol: "doseme.mantar_kolon_baslik_alani", etiket: "Mantar kolon başlık alanı (m²)", tip: "number", adim: 0.05, panel: "tam", bolum: "Döşeme" },
  { yol: "merdiven.riht", etiket: "Merdiven rıht (m)", tip: "number", adim: 0.001, panel: "tam", bolum: "Merdiven" },
  { yol: "merdiven.basamak", etiket: "Merdiven basamak (m)", tip: "number", adim: 0.001, panel: "tam", bolum: "Merdiven" },
  { yol: "merdiven.kalinlik", etiket: "Merdiven plak kalınlığı (m)", tip: "number", adim: 0.01, panel: "tam", bolum: "Merdiven" },
  { yol: "merdiven.egim_katsayisi", etiket: "Merdiven eğim katsayısı (0=otomatik)", tip: "number", adim: 0.01, panel: "tam", bolum: "Merdiven" },
];

["kolon", "perde", "kiris", "doseme", "merdiven"].forEach((k) => {
  ALANLAR.push({ yol: `donati.katsayilar.${k}`, etiket: `Demir — ${k} (kg/m³)`, tip: "number", adim: 1, panel: "tam", bolum: "Donatı" });
});

["kolon_beton", "kolon_kalip", "perde_beton", "perde_kalip", "kiris_beton", "kiris_kalip",
 "doseme_beton", "doseme_kalip", "merdiven_beton", "merdiven_kalip", "demir",
 "kapi", "pencere", "siva", "siva_tavan", "kaplama"].forEach((p) => {
  ALANLAR.push({ yol: `pozlar.${p}`, etiket: `Poz — ${p.replace(/_/g, " ")}`, tip: "metin", panel: "tam", bolum: "Pozlar" });
});

["kolon", "perde", "kiris", "doseme", "merdiven", "bosluk", "kapi", "pencere", "metin", "yoksay"].forEach((k) => {
  ALANLAR.push({ yol: `katmanlar.${k}`, etiket: `Katman — ${k} (regex, virgülle)`, tip: "liste", panel: "tam", bolum: "Katmanlar" });
});

[
  { yol: "siva.aktif", etiket: "Sıva / badana (m²) — YAKLAŞIK", tip: "onay", panel: "tam", bolum: "Sıva/Kaplama" },
  { yol: "siva.yuzey_dusumu", etiket: "Sıva yüzey düşümü", tip: "number", adim: 0.05, panel: "tam", bolum: "Sıva/Kaplama" },
  { yol: "kaplama.aktif", etiket: "Döşeme kaplama + tesviye (m²) — YAKLAŞIK", tip: "onay", panel: "tam", bolum: "Sıva/Kaplama" },
  { yol: "kapi.aktif", etiket: "Kapı doğrulama listesi (adet)", tip: "onay", panel: "tam", bolum: "Doğrulama" },
  { yol: "pencere.aktif", etiket: "Pencere doğrulama listesi (adet)", tip: "onay", panel: "tam", bolum: "Doğrulama" },
].forEach((a) => ALANLAR.push(a));

/* ---------------- Durum ---------------- */

const DURUM = {
  varsayilan: null,
  yapilandirma: null,
  aktifSekme: "metraj",
  sonSatirlar: null,
  sonKaynak: "",
};

/* ---------------- Form uretici ---------------- */

function alanHtml(a) {
  const deger = yolOku(DURUM.yapilandirma, a.yol, "");
  let girdi;
  if (a.tip === "select") {
    const sec = a.secenekler.map((s) =>
      `<option value="${s}" ${String(deger) === s ? "selected" : ""}>${s}</option>`).join("");
    girdi = `<select data-yol="${a.yol}">${sec}</select>`;
  } else if (a.tip === "onay") {
    girdi = `<label class="anahtar"><input type="checkbox" data-yol="${a.yol}" ${deger ? "checked" : ""}><span class="kaydirici"></span></label>`;
  } else if (a.tip === "liste") {
    const metin = Array.isArray(deger) ? deger.join(", ") : "";
    girdi = `<input type="text" data-yol="${a.yol}" data-liste="1" value="${esc(metin)}" placeholder="^KOLON, ^S-KOL">`;
  } else {
    const tip = a.tip === "number" ? "number" : "text";
    girdi = `<input type="${tip}" data-yol="${a.yol}" ${a.adim ? `step="${a.adim}"` : ""} value="${esc(deger)}">`;
  }
  return `<label class="alan">${a.etiket}${girdi}</label>`;
}

function formlariBagla(kapsam) {
  $$("[data-yol]", kapsam).forEach((girdi) => {
    girdi.addEventListener("input", () => {
      const yol = girdi.dataset.yol;
      let deger = undefined;
      if (girdi.type === "checkbox") deger = girdi.checked;
      else if (girdi.type === "number") {
        const n = parseFloat(girdi.value);
        if (!Number.isFinite(n)) {
          girdi.value = yolOku(DURUM.yapilandirma, yol, "") ?? "";
          return;
        }
        deger = n;
      } else if (girdi.dataset.liste) deger = girdi.value.split(",").map((s) => s.trim()).filter(Boolean);
      else deger = girdi.value;
      if (deger !== undefined) yolAyarla(DURUM.yapilandirma, yol, deger);
    });
  });
}

function hizliFormlariYenile() {
  $("#metraj-hizli-form").innerHTML =
    ALANLAR.filter((a) => a.panel === "hizli").map(alanHtml).join("");
  $("#toplu-hizli-form").innerHTML =
    ALANLAR.filter((a) => a.panel === "hizli").map(alanHtml).join("");
  formlariBagla($("#metraj-hizli-form"));
  formlariBagla($("#toplu-hizli-form"));
}

function katAlanlariniYenile() {
  $("#metraj-kat-yuk").value = yolOku(DURUM.yapilandirma, "kat.kat_yuksekligi", 3.0);
  $("#metraj-doseme-kal").value = yolOku(DURUM.yapilandirma, "kat.doseme_kalinligi", 0.15);
  $("#toplu-kat-yuk").value = yolOku(DURUM.yapilandirma, "kat.kat_yuksekligi", 3.0);
  $("#toplu-doseme-kal").value = yolOku(DURUM.yapilandirma, "kat.doseme_kalinligi", 0.15);
}

function katAlanlariniBagla() {
  const esle = [
    ["metraj-kat-yuk", "kat.kat_yuksekligi"],
    ["metraj-doseme-kal", "kat.doseme_kalinligi"],
    ["toplu-kat-yuk", "kat.kat_yuksekligi"],
    ["toplu-doseme-kal", "kat.doseme_kalinligi"],
  ];
  esle.forEach(([id, yol]) => {
    $(`#${id}`).addEventListener("input", () => {
      const el = $(`#${id}`);
      const n = parseFloat(el.value);
      if (!Number.isFinite(n)) {
        el.value = yolOku(DURUM.yapilandirma, yol, "") ?? "";
        return;
      }
      yolAyarla(DURUM.yapilandirma, yol, n);
    });
  });
}

function ayarlarFormuYenile() {
  const kapsayici = $("#ayar-form");
  let html = "";
  let sonBolum = null;
  ALANLAR.forEach((a) => {
    if (a.bolum !== sonBolum) {
      html += `<div class="ayar-bolum">${a.bolum}</div>`;
      sonBolum = a.bolum;
    }
    html += alanHtml(a);
  });
  kapsayici.innerHTML = html;
  formlariBagla(kapsayici);
}

/* ---------------- Sekmeler ---------------- */

function sekmeAc(ad) {
  DURUM.aktifSekme = ad;
  $$(".menu-ogesi").forEach((b) => b.classList.toggle("aktif", b.dataset.sekme === ad));
  $$(".sekme").forEach((s) => s.classList.toggle("aktif", s.id === `sekme-${ad}`));
  if (ad === "ayarlar") ayarlarFormuYenile();
  else if (ad === "metraj" || ad === "toplu") {
    hizliFormlariYenile();
    katAlanlariniYenile();
  }
}

/* ---------------- Birakma alanlari ---------------- */

function birakAlaniYukle(birak, girdi, onSecim) {
  const goster = (ad) => {
    $(".birak-metin", birak).innerHTML = ad ? `<strong>${esc(ad)}</strong>` : "<strong>Dosyayı sürükleyip bırakın</strong> veya tıklayıp seçin";
    birak.classList.toggle("dolu", Boolean(ad));
  };
  birak.addEventListener("click", () => girdi.click());
  birak.addEventListener("dragover", (e) => { e.preventDefault(); birak.classList.add("surukle"); });
  birak.addEventListener("dragleave", () => birak.classList.remove("surukle"));
  birak.addEventListener("drop", (e) => {
    e.preventDefault();
    birak.classList.remove("surukle");
    const f = e.dataTransfer.files[0];
    if (f) { girdi.files = e.dataTransfer.files; onSecim(f); goster(f.name); }
  });
  girdi.addEventListener("change", () => {
    const f = girdi.files[0];
    if (f) { onSecim(f); goster(f.name); }
  });
  return goster;
}

/* ---------------- Metraj ---------------- */

function sonucJsonTemiz(s) {
  const k = Object.assign({}, s);
  delete k.svg; delete k.excel_b64;
  return JSON.stringify(k, null, 2);
}

function ozetKartlariHtml(ozet) {
  let html = "";
  const toplam = { beton: 0, kalip: 0, demir: 0 };
  TIP_SIRA.forEach((tip) => {
    const k = ozet[tip];
    if (!k) return;
    if (!(k.adet || k.beton_m3 || k.kalip_m2 || k.demir_kg)) return;
    toplam.beton += k.beton_m3; toplam.kalip += k.kalip_m2; toplam.demir += k.demir_kg;
    html += `<div class="ozet-kart">
      <div class="ozet-renk" style="background:${TIP_RENKLER[tip] || "#999"}"></div>
      <div style="flex:1">
        <div class="ozet-ad">${tip} <span class="ozet-adet">${k.adet} adet</span></div>
        <div class="ozet-deger">
          <span>Beton <b>${sayiFormat(k.beton_m3, 3)}</b> m³</span>
          <span>Kalıp <b>${sayiFormat(k.kalip_m2, 3)}</b> m²</span>
          ${k.demir_kg ? `<span>Demir <b>${sayiFormat(k.demir_kg, 2)}</b> kg</span>` : ""}
        </div>
      </div></div>`;
  });
  html += `<div class="ozet-kart ozet-toplam">
    <div class="ozet-renk" style="background:#2e7dd1"></div>
    <div style="flex:1">
      <div class="ozet-ad">TOPLAM</div>
      <div class="ozet-deger">
        <span>Beton <b>${sayiFormat(toplam.beton, 3)}</b> m³</span>
        <span>Kalıp <b>${sayiFormat(toplam.kalip, 3)}</b> m²</span>
        ${toplam.demir ? `<span>Demir <b>${sayiFormat(toplam.demir, 2)}</b> kg</span>` : ""}
      </div>
    </div></div>`;
  return html;
}

function uyarilarHtml(uyarilar) {
  if (!uyarilar || !uyarilar.length) return "";
  return `<div class="uyari-kutu">
    <div class="uyari-kutu-baslik">⚠ UYARILAR (${uyarilar.length}) — teslim öncesi kontrol edin</div>
    <ul>${uyarilar.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></div>`;
}

function hucre(deger, basamak) {
  if (deger === null || deger === undefined) return "<td></td>";
  return `<td class="vurgulu">${sayiFormat(deger, basamak)}</td>`;
}

function satirHtml(s) {
  const detay = (s.detay || []).length
    ? `<tr class="detay-satiri" hidden><td colspan="12">${s.detay.map(esc).join(" &nbsp;•&nbsp; ")}</td></tr>`
    : "";
  return `
  <tr class="satir-ana ${s.dusum ? "dusum" : ""}">
    <td class="sol">${esc(s.poz)}</td>
    <td class="sol">${esc(s.eleman)}</td>
    <td class="sol">${esc(s.tanim)}</td>
    ${hucre(s.benzer, 0)}
    ${hucre(s.en, 3)}
    ${hucre(s.boy, 3)}
    ${hucre(s.yukseklik, 3)}
    ${hucre(s.alan, 3)}
    ${hucre(s.hacim, 3)}
    ${hucre(s.demir, 2)}
    <td>${esc(s.birim)}</td>
    <td class="sol" style="white-space:normal;min-width:200px">${esc(s.formul)}</td>
  </tr>${detay}`;
}

function toplamlar(satirlar) {
  const t = { beton: 0, kalip: 0, demir: 0 };
  satirlar.forEach((s) => {
    const isaret = s.dusum ? -1 : 1;
    if (s.birim === "m3") t.beton += isaret * (s.hacim || 0);
    else if (s.birim === "m2") t.kalip += isaret * (s.alan || 0);
    else if (s.birim === "kg") t.demir += isaret * (s.demir || 0);
  });
  return t;
}

function cetvelHtml(satirlar, katli) {
  let html = "";
  const grupla = (liste, etiket) => {
    html += `<tr class="grup"><td colspan="12">${etiket}</td></tr>`;
    liste.forEach((s) => { html += satirHtml(s); });
  };
  if (katli) {
    const katlar = [...new Set(satirlar.map((s) => s.kat || "?"))];
    katlar.forEach((kat) => {
      const katSatirlari = satirlar.filter((s) => (s.kat || "?") === kat);
      TIP_SIRA.forEach((tip) => {
        const grup = katSatirlari.filter((s) => s.tip === tip);
        if (grup.length) grupla(grup, `KAT: ${esc(kat)} — ${tip.toUpperCase()}`);
      });
    });
  } else {
    TIP_SIRA.forEach((tip) => {
      const grup = satirlar.filter((s) => s.tip === tip);
      if (grup.length) grupla(grup, `${tip.toUpperCase()} METRAJI`);
    });
  }
  const t = toplamlar(satirlar);
  html += `<tr class="toplam">
    <td class="sol" colspan="3">TOPLAM</td><td></td><td></td><td></td><td></td>
    <td class="vurgulu">${sayiFormat(t.kalip, 3)}</td>
    <td class="vurgulu">${sayiFormat(t.beton, 3)}</td>
    <td class="vurgulu">${sayiFormat(t.demir, 2)}</td>
    <td></td><td></td></tr>`;
  return html;
}

function cetvelTablosu(satirlar, katli) {
  return `<div class="bolum-baslik">📋 Metraj Cetveli</div>
  <div class="tablo-kapsayici">
    <table class="metraj">
      <thead><tr>
        <th class="sol">Poz</th><th class="sol">Eleman</th><th class="sol">Tanım</th>
        <th>Benzer</th><th>En (m)</th><th>Boy (m)</th><th>Yük. (m)</th>
        <th>Alan (m²)</th><th>Hacim (m³)</th><th>Demir (kg)</th><th>Birim</th><th class="sol">Formül</th>
      </tr></thead>
      <tbody>${cetvelHtml(satirlar, katli)}</tbody>
    </table>
  </div>`;
}

function sonucTablosunuBagla() {
  $$(".tablo-kapsayici tbody tr.satir-ana").forEach((satir) => {
    satir.addEventListener("click", () => {
      satir.classList.toggle("acik");
      const detay = satir.nextElementSibling;
      if (detay && detay.classList.contains("detay-satiri")) detay.hidden = !detay.hidden;
    });
  });
}

function parametreHtml(p) {
  if (!p) return "";
  return `<div class="parametre">
    <span>Kat yük. <b>${sayiFormat(p.kat_yuksekligi, 2)} m</b></span>
    <span>Döşeme <b>${sayiFormat(p.doseme_kalinligi, 2)} m</b></span>
    <span>Net yük. <b>${sayiFormat(p.net_yukseklik, 2)} m</b></span>
    <span>Birim <b>${esc(p.birim)}</b></span>
  </div>`;
}

function maliyetOzetHtml(m) {
  if (!m || !m.kalemler || !m.kalemler.length) return "";
  const rows = m.kalemler.slice(0, 8).map((k) => `<tr>
    <td class="sol">${esc(k.poz)}</td>
    <td class="sol">${esc(k.tanim)}</td>
    <td>${sayiFormat(k.miktar, 2)} ${esc(k.birim)}</td>
    <td>${sayiFormat(k.fiyat, 2)}</td>
    <td class="vurgulu">${sayiFormat(k.tutar, 2)}</td>
  </tr>`).join("");
  const ekstra = m.kalemler.length > 8
    ? `<tr><td colspan="5" class="sol">… ve ${m.kalemler.length - 8} kalem daha (Maliyet sekmesinde tamamı)</td></tr>` : "";
  const eksik = m.fiyatsiz_pozlar && m.fiyatsiz_pozlar.length
    ? `<div class="uyari-kutu"><div class="uyari-kutu-baslik">Fiyat tanımsız pozlar</div>
       <ul><li>${m.fiyatsiz_pozlar.map(esc).join(", ")}</li></ul></div>` : "";
  return `<div class="bolum-baslik">💰 Yaklaşık Maliyet (${esc(m.para_birimi)})</div>
  <div class="tablo-kapsayici"><table class="metraj">
    <thead><tr>
      <th class="sol">Poz</th><th class="sol">Tanım</th>
      <th>Miktar</th><th>Birim Fiyat</th><th>Tutar</th>
    </tr></thead>
    <tbody>${rows}${ekstra}</tbody></table></div>
  <div class="maliyet-toplam">
    <span>Ara toplam <b>${sayiFormat(m.ara_toplam, 2)}</b></span>
    <span>KDV (%${m.kdv_oran}) <b>${sayiFormat(m.kdv, 2)}</b></span>
    <span>GENEL TOPLAM <b>${sayiFormat(m.genel_toplam, 2)} ${esc(m.para_birimi)}</b></span>
  </div>
  <p class="maliyet-not">${esc(m.not)}</p>
  ${eksik}`;
}

function katMaliyetiHtml(km) {
  if (!km || !km.length) return "";
  const rows = km.map((k) => `<tr>
    <td class="sol"><b>${esc(k.kat)}</b></td>
    <td class="vurgulu">${sayiFormat(k.ara_toplam, 2)}</td>
    <td>${sayiFormat(k.kdv, 2)}</td>
    <td class="vurgulu"><b>${sayiFormat(k.genel_toplam, 2)}</b></td>
    <td class="sol">${(k.fiyatsiz_pozlar || []).length
      ? `<span style="color:#b03a2e">${k.fiyatsiz_pozlar.length} fiyatsız poz</span>`
      : ""}</td>
  </tr>`).join("");
  return `<div class="bolum-baslik">💰 Kat Bazında Yaklaşık Maliyet</div>
  <div class="tablo-kapsayici"><table class="metraj">
    <thead><tr>
      <th class="sol">Kat</th><th>Ara Toplam</th><th>KDV</th><th>Genel Toplam</th><th>Not</th>
    </tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function metrajSonucuGoster(sonuc, ad, kapsayici) {
  const alan = kapsayici || $("#metraj-sonuc");
  const ozet = ozetKartlariHtml(sonuc.ozet);
  const uyari = uyarilarHtml(sonuc.uyarilar);
  const cetvel = cetvelTablosu(sonuc.satirlar, false);
  const pafta = sonuc.svg
    ? `<div class="bolum-baslik">🖼️ Kontrol Paftası</div>
       <div class="pafta-kapsayici">
         <img src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(sonuc.svg)}" alt="Kontrol paftası">
       </div>`
    : "";

  alan.innerHTML = `
    <div class="sonuc-ust">
      <div class="sonuc-ust-bilgi">
        <h2>${esc(sonuc.kat || "Metraj")} <span class="badge badge-kat">${esc(ad)}</span></h2>
        <p>${esc(sonuc.kaynak_dosya || "")}</p>
        ${parametreHtml(sonuc.parametreler)}
      </div>
      <div class="indir-butonlar">
        <button class="ikincil" data-indir="excel">Excel</button>
        <button class="ikincil" data-indir="json">JSON</button>
        <button class="ikincil" data-indir="svg">SVG Pafta</button>
      </div>
    </div>
    <div class="ozet-grid">${ozet}</div>
    ${uyari}
    ${cetvel}
    ${maliyetOzetHtml(sonuc.maliyet)}
    ${pafta}`;
  alan.hidden = false;
  sonucTablosunuBagla();

  $$(".indir-butonlar button", alan).forEach((b) => {
    b.addEventListener("click", () => {
      const taban = `${dosyaAdiTemiz(ad)}.metraj`;
      if (b.dataset.indir === "excel") {
        indirB64(sonuc.excel_b64, `${taban}.xlsx`,
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
      } else if (b.dataset.indir === "json") {
        indirMetin(sonucJsonTemiz(sonuc), `${taban}.json`, "application/json");
      } else {
        indirMetin(sonuc.svg, `${taban}.kontrol.svg`, "image/svg+xml");
      }
    });
  });
}

async function metrajCalistir() {
  const girdi = $("#metraj-dosya");
  const dosya = girdi.files[0];
  if (!dosya) { bildirim("Lütfen bir plan dosyası seçin.", "hata"); return; }

  const fd = new FormData();
  fd.append("dosya", dosya);
  fd.append("ayarlar", JSON.stringify(DURUM.yapilandirma));
  const ek = {
    kat_adi: $("#metraj-kat-adi").value,
    olcek: $("#metraj-olcek").value,
    sayfa: $("#metraj-sayfa").value,
    kalibre: $("#metraj-kalibre").value,
  };
  Object.entries(ek).forEach(([k, v]) => { if (v) fd.append(k, v); });

  const spinner = $("#metraj-yukleniyor");
  const hata = $("#metraj-hata");
  const sonuc = $("#metraj-sonuc");
  const bos = $("#metraj-bos");
  spinner.hidden = false; hata.hidden = true; sonuc.hidden = true; bos.hidden = true;

  try {
    const veri = await api("/api/metraj", { method: "POST", body: fd });
    DURUM.sonSatirlar = veri.satirlar;
    DURUM.sonKaynak = dosya.name;
    metrajSonucuGoster(veri, dosya.name);
    bildirim("Metraj hazır.");
  } catch (e) {
    hata.textContent = "Hata: " + e.message;
    hata.hidden = false;
    bos.hidden = false;
  } finally {
    spinner.hidden = true;
  }
}

/* ---------------- Toplu ---------------- */

function topluSatirEkle(girdiKayit) {
  const satir = document.createElement("div");
  satir.className = "toplu-satir";
  satir.innerHTML = `
    <div class="birak-alani toplu-birak">
      <input type="file" accept=".dwg,.dxf,.pdf" hidden>
      <div class="birak-ikon">⬆</div>
      <p class="birak-metin"><strong>Dosya seçin</strong> veya sürükleyin</p>
    </div>
    <label class="alan">Kat adı<input type="text" placeholder="3. Normal Kat"></label>
    <button class="toplu-sil" title="Kaldır">×</button>`;
  $("#toplu-dosyalar").appendChild(satir);

  const girdi = $("input[type=file]", satir);
  const birak = $(".toplu-birak", satir);
  const sil = $(".toplu-sil", satir);
  const kat = $("input[type=text]", satir);

  if (girdiKayit) {
    kat.value = girdiKayit.kat || "";
    if (girdiKayit.ad) $(".birak-metin", birak).innerHTML = `<strong>${esc(girdiKayit.ad)}</strong>`;
  }
  birakAlaniYukle(birak, girdi, (f) => {
    $(".birak-metin", birak).innerHTML = `<strong>${esc(f.name)}</strong>`;
    birak.classList.add("dolu");
  });
  sil.addEventListener("click", () => satir.remove());
}

function topluSatirlariOku() {
  const satirlar = [];
  $$("#toplu-dosyalar .toplu-satir").forEach((r) => {
    const g = $("input[type=file]", r);
    if (g.files[0]) satirlar.push({ dosya: g.files[0], kat: $("input[type=text]", r).value.trim() });
  });
  return satirlar;
}

function ozetTopla(ozet, anahtar) {
  return TIP_SIRA.reduce((a, tip) => a + (ozet[tip] ? ozet[tip][anahtar] || 0 : 0), 0);
}

function katOzetiTablosu(veri) {
  const sutunlar = ["Kolon", "Perde", "Kiris", "Doseme", "Merdiven"];
  const al = (ozet, tip, anahtar) => (ozet[tip] ? ozet[tip][anahtar] || 0 : 0);
  let rows = "";
  veri.katlar.forEach((k) => {
    rows += `<tr>
      <td class="sol">${esc(k.kat)} <span class="badge badge-kat">${esc(k.kaynak_dosya)}</span></td>
      ${sutunlar.map((t) => `<td class="vurgulu">${sayiFormat(al(k.ozet, t, "beton_m3"), 3)}</td>`).join("")}
      <td class="vurgulu"><b>${sayiFormat(ozetTopla(k.ozet, "beton_m3"), 3)}</b></td>
      <td class="vurgulu">${sayiFormat(ozetTopla(k.ozet, "kalip_m2"), 3)}</td>
      <td class="vurgulu">${sayiFormat(ozetTopla(k.ozet, "demir_kg"), 2)}</td>
    </tr>`;
  });
  rows += `<tr class="toplam">
    <td class="sol">TOPLAM</td>
    ${sutunlar.map((t) => `<td class="vurgulu">${sayiFormat(al(veri.toplam, t, "beton_m3"), 3)}</td>`).join("")}
    <td class="vurgulu"><b>${sayiFormat(ozetTopla(veri.toplam, "beton_m3"), 3)}</b></td>
    <td class="vurgulu">${sayiFormat(ozetTopla(veri.toplam, "kalip_m2"), 3)}</td>
    <td class="vurgulu">${sayiFormat(ozetTopla(veri.toplam, "demir_kg"), 2)}</td>
  </tr>`;

  return `<div class="bolum-baslik">🏢 Kat Özeti</div>
  <div class="tablo-kapsayici"><table class="metraj">
    <thead><tr>
      <th class="sol">Kat</th>
      ${sutunlar.map((t) => `<th>${t} m³</th>`).join("")}
      <th>Beton m³</th><th>Kalıp m²</th><th>Demir kg</th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
}

function topluSonucuGoster(veri) {
  const alan = $("#toplu-sonuc");
  const katOzet = katOzetiTablosu(veri);
  const kartlar = ozetKartlariHtml(veri.toplam);
  const uyari = uyarilarHtml(veri.uyarilar);
  const cetvel = cetvelTablosu(veri.satirlar, true);
  const katMaliyet = katMaliyetiHtml(veri.kat_maliyetleri);

  alan.innerHTML = `
    <div class="sonuc-ust">
      <div class="sonuc-ust-bilgi">
        <h2>Toplu Metraj <span class="badge badge-kat">${veri.katlar.length} kat</span></h2>
        <p>Tüm katların ortak metraj cetveli</p>
      </div>
      <div class="indir-butonlar">
        <button class="ikincil" data-indir="excel">Excel</button>
        <button class="ikincil" data-indir="json">JSON</button>
      </div>
    </div>
    ${katOzet}
    <div class="ozet-grid">${kartlar}</div>
    ${katMaliyet}
    ${uyari}
    ${cetvel}
    ${maliyetOzetHtml(veri.maliyet)}`;
  alan.hidden = false;
  sonucTablosunuBagla();

  $$("#toplu-sonuc .indir-butonlar button").forEach((b) => {
    b.addEventListener("click", () => {
      const taban = "toplu";
      if (b.dataset.indir === "excel") {
        indirB64(veri.excel_b64, `${taban}.toplu.xlsx`,
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
      } else {
        const k = Object.assign({}, veri); delete k.excel_b64;
        indirMetin(JSON.stringify(k, null, 2), `${taban}.toplu.json`, "application/json");
      }
    });
  });
}

async function topluCalistir() {
  const katlar = topluSatirlariOku();
  if (!katlar.length) { bildirim("En az bir dosya ekleyin.", "hata"); return; }

  const fd = new FormData();
  katlar.forEach((k) => fd.append("dosyalar", k.dosya));
  fd.append("kat_adlari", JSON.stringify(katlar.map((k) => k.kat)));
  fd.append("ayarlar", JSON.stringify(DURUM.yapilandirma));
  const ek = {
    olcek: $("#toplu-olcek").value,
    kalibre: $("#toplu-kalibre").value,
  };
  Object.entries(ek).forEach(([k, v]) => { if (v) fd.append(k, v); });

  const spinner = $("#toplu-yukleniyor");
  const hata = $("#toplu-hata");
  const sonuc = $("#toplu-sonuc");
  const bos = $("#toplu-bos");
  spinner.hidden = false; hata.hidden = true; sonuc.hidden = true; bos.hidden = true;

  try {
    const veri = await api("/api/toplu", { method: "POST", body: fd });
    DURUM.sonSatirlar = veri.satirlar;
    DURUM.sonKaynak = `${katlar.length} kat`;
    topluSonucuGoster(veri);
    bildirim("Toplu metraj hazır.");
  } catch (e) {
    hata.textContent = "Hata: " + e.message;
    hata.hidden = false;
    bos.hidden = false;
  } finally {
    spinner.hidden = true;
  }
}

/* ---------------- PDF İncele ---------------- */

function pdfInceleSonucuGoster(bilgi) {
  const alan = $("#pdf-sonuc");
  let renkler = "";
  if (bilgi.renkler && bilgi.renkler.length) {
    const satirlar = bilgi.renkler.map((r) => `
      <tr>
        <td><span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${esc(r.renk)};border:1px solid #ccc;vertical-align:middle"></span> ${esc(r.renk)}</td>
        <td class="vurgulu">${sayiFormat(r.kalinlik, 2)}</td>
        <td class="vurgulu">${r.adet}</td>
        <td class="vurgulu">${sayiFormat(r.toplam_uzunluk_pt, 1)}</td>
        <td class="sol">${esc(r.turler)}</td>
      </tr>`).join("");
    const esleme = bilgi.renkler.map((r) => `      "${r.renk}": kolon`).join("\n");
    renkler = `<div class="tablo-kapsayici"><table class="metraj">
      <thead><tr><th class="sol">Renk</th><th>Kalınlık (pt)</th><th>Adet</th><th>Toplam pt</th><th class="sol">Türler</th></tr></thead>
      <tbody>${satirlar}</tbody></table></div>
      <div class="uyari-kutu"><div class="uyari-kutu-baslik">💡 Önerilen renk eşlemesi (Ayarlar → Gelişmiş YAML)</div>
      <pre style="font-size:12px;overflow:auto">pdf:\n  renk_esleme:\n${esc(esleme)}</pre></div>`;
  } else {
    renkler = `<div class="uyari-kutu"><div class="uyari-kutu-baslik">Vektör çizgi bulunamadı</div>
      Bu PDF taranmış (görüntü) olabilir; metraj çıkarılamaz.</div>`;
  }
  alan.innerHTML = `
    <div class="sonuc-ust"><div class="sonuc-ust-bilgi">
      <h2>${esc(bilgi.dosya || "PDF")}</h2>
      <p>Sayfa ${bilgi.sayfa || "?"} / ${bilgi.sayfa_sayisi || "?"} &nbsp;•&nbsp; ${sayiFormat(bilgi.genislik_mm, 1)} × ${sayiFormat(bilgi.yukseklik_mm, 1)} mm &nbsp;•&nbsp; ${bilgi.yazi_sayisi || 0} karakter</p>
    </div></div>
    ${renkler}`;
  alan.hidden = false;
}

async function pdfIncele() {
  const girdi = $("#pdf-dosya");
  const dosya = girdi.files[0];
  if (!dosya) { bildirim("Lütfen bir PDF seçin.", "hata"); return; }
  const fd = new FormData();
  fd.append("dosya", dosya);
  fd.append("sayfa", $("#pdf-sayfa").value || "1");

  const spinner = $("#pdf-yukleniyor");
  const hata = $("#pdf-hata");
  const sonuc = $("#pdf-sonuc");
  const bos = $("#pdf-bos");
  spinner.hidden = false; hata.hidden = true; sonuc.hidden = true; bos.hidden = true;
  try {
    const bilgi = await api("/api/pdf-incele", { method: "POST", body: fd });
    pdfInceleSonucuGoster(bilgi);
  } catch (e) {
    hata.textContent = "Hata: " + e.message;
    hata.hidden = false;
    bos.hidden = false;
  } finally {
    spinner.hidden = true;
  }
}

/* ---------------- Eslestirme ---------------- */

const ESLE_TIPLER = [
  { deger: "", etiket: "— Sezgisel (eşleme yok) —" },
  { deger: "kolon", etiket: "Kolon" },
  { deger: "perde", etiket: "Perde" },
  { deger: "kiris", etiket: "Kiriş" },
  { deger: "doseme", etiket: "Döşeme" },
  { deger: "merdiven", etiket: "Merdiven" },
  { deger: "bosluk", etiket: "Boşluk" },
  { deger: "yoksay", etiket: "Yoksay (metraja girmez)" },
];

let ESLE_DURUM = { tur: null, dosya: null, adaylar: [] };

function esleTipSecenekleri(secili) {
  return ESLE_TIPLER.map((t) =>
    `<option value="${t.deger}" ${t.deger === (secili || "") ? "selected" : ""}>${t.etiket}</option>`
  ).join("");
}

function esleAdaylariGoster(veri) {
  const alan = $("#esle-adaylar");
  const baslik = veri.tur === "renk"
    ? "PDF Renkleri — her renge bir eleman tipi seçin"
    : "Katmanlar — her katmana bir eleman tipi seçin";
  const satirlar = veri.adaylar.map((a, i) => {
    const isim = veri.tur === "renk"
      ? `<span class="renk-kutu" style="background:${esc(a.anahtar)}"></span> ${esc(a.anahtar)}`
      : `<span class="katman-kutu">${esc(a.anahtar)}</span>`;
    const durum = a.suanki_tip
      ? `<span class="esle-durum esle-durum-tamam">şu an: ${esc(a.suanki_tip)}</span>`
      : (a.oneri_tip
          ? `<span class="esle-durum esle-durum-oneri">öneri: ${esc(a.oneri_tip)}</span>`
          : `<span class="esle-durum esle-durum-yok">eşlenmemiş</span>`);
    const detay = a.aciklama
      ? `<div class="esle-aciklama">${esc(a.aciklama)}</div>`
      : "";
    return `<tr>
      <td class="sol">${isim}</td>
      <td class="sol">${detay}</td>
      <td class="vurgulu">${a.adet}</td>
      <td>${durum}</td>
      <td><select data-esle-aday="${i}">${esleTipSecenekleri(a.suanki_tip || a.oneri_tip)}</select></td>
    </tr>`;
  }).join("");
  const acik = veri.tur === "renk"
    ? "Kırmızı/yeşil Sta4CAD dolgu renkleri için otomatik 'Yoksay' önerildi; mavi hatlar sezgisel bırakılırsa büyük kapalı alanlar döşeme sayılır."
    : "Önerilenler otomatik işaretlendi; sezgisel bırakılan katmanlar geometrik tahminle işlenir.";
  alan.innerHTML = `
    <div class="bolum-baslik">${baslik}</div>
    <div class="esle-ozet">
      Toplam <b>${veri.toplam_adet}</b> varlık — <b class="${veri.eslenmeyen_adet ? "esle-kirmizi" : ""}">${veri.eslenmeyen_adet}</b> adedi şu an eşlenmemiş
      &nbsp;•&nbsp; ${acik}
    </div>
    <div class="tablo-kapsayici"><table class="metraj">
      <thead><tr><th class="sol">Renk / Katman</th><th class="sol">Detay</th><th>Adet</th><th>Durum</th><th>Eleman Tipi</th></tr></thead>
      <tbody>${satirlar}</tbody></table></div>`;
  $("#esle-icerik").hidden = false;
  $("#esle-uygula-alan").hidden = false;
}

function esleEslemeleriOku() {
  const esleme = {};
  $$("#esle-adaylar select[data-esle-aday]").forEach((sel) => {
    const a = ESLE_DURUM.adaylar[Number(sel.dataset.esleAday)];
    if (a && sel.value) esleme[a.anahtar] = sel.value;
  });
  return esleme;
}

function esleFormData(dosya) {
  const fd = new FormData();
  fd.append("dosya", dosya);
  fd.append("ayarlar", JSON.stringify(DURUM.yapilandirma));
  const s = $("#esle-sayfa").value;
  if (s && s !== "1") fd.append("sayfa", s);
  return fd;
}

async function esleTara() {
  const girdi = $("#esle-dosya");
  const dosya = girdi.files[0];
  if (!dosya) { bildirim("Lütfen bir plan dosyası seçin.", "hata"); return; }

  const spinner = $("#esle-yukleniyor");
  const hata = $("#esle-hata");
  const icerik = $("#esle-icerik");
  const bos = $("#esle-bos");
  spinner.hidden = false; hata.hidden = true; icerik.hidden = true; bos.hidden = true;
  $("#esle-uygula-alan").hidden = true;

  try {
    const veri = await api("/api/esle-tara", { method: "POST", body: esleFormData(dosya) });
    ESLE_DURUM = { tur: veri.tur, dosya, adaylar: veri.adaylar };
    esleAdaylariGoster(veri);
  } catch (e) {
    hata.textContent = "Hata: " + e.message;
    hata.hidden = false;
    bos.hidden = false;
  } finally {
    spinner.hidden = true;
  }
}

async function esleMetrajHesapla(dosya) {
  const alan = $("#esle-sonuc");
  alan.hidden = false;
  alan.innerHTML = `<div class="yukleniyor" style="padding:24px"><div class="spinner"></div> Metraj hesaplanıyor…</div>`;
  try {
    const veri = await api("/api/metraj", { method: "POST", body: esleFormData(dosya) });
    DURUM.sonSatirlar = veri.satirlar;
    DURUM.sonKaynak = dosya.name;
    metrajSonucuGoster(veri, dosya.name, alan);
    bildirim("Eslemeler uygulandı, metraj hazır.");
  } catch (e) {
    alan.innerHTML = `<div class="hata-kutusu">Hata: ${esc(e.message)}</div>`;
  }
}

async function esleUygula() {
  const dosya = ESLE_DURUM.dosya;
  if (!dosya) { bildirim("Önce dosyayı tarayın.", "hata"); return; }
  const esleme = esleEslemeleriOku();
  if (ESLE_DURUM.tur === "renk") yolAyarla(DURUM.yapilandirma, "pdf.renk_esleme", esleme);
  else yolAyarla(DURUM.yapilandirma, "katmanlar.kesin", esleme);

  try {
    const dt = new DataTransfer();
    dt.items.add(dosya);
    $("#metraj-dosya").files = dt.files;
    $(".birak-metin", $("#metraj-birak")).innerHTML = `<strong>${esc(dosya.name)}</strong>`;
    $("#metraj-birak").classList.add("dolu");
  } catch (_) { /* eslemenin uygulanmasi metraj icin yeterli */ }

  await esleMetrajHesapla(dosya);
}

async function esleYamlIndir() {
  try {
    indirMetin(await yamlUret(), "hakedis-esleme.yml", "application/yaml");
    bildirim("YAML indirildi; ofis.yml olarak kaydedip --config ile kullanın.");
  } catch (e) { bildirim("YAML üretilemedi: " + e.message, "hata"); }
}

/* ---------------- Ayarlar ---------------- */

async function yamlUret() {
  const y = await api("/api/yaml-uret", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ayarlar: DURUM.yapilandirma }),
  });
  return y.yaml;
}

async function yamlCoz(metin) {
  const y = await api("/api/yaml-coz", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yaml: metin }),
  });
  return y.ayarlar;
}

function ayarlariYenile() {
  DURUM.yapilandirma = derinKopya(DURUM.varsayilan);
  ayarlarFormuYenile();
  hizliFormlariYenile();
  katAlanlariniYenile();
  bildirim("Varsayılan ayarlar yüklendi.");
}

function ayarFormlariniYenile() {
  ayarlarFormuYenile();
  hizliFormlariYenile();
  katAlanlariniYenile();
}

/* ---------------- Maliyet ---------------- */

function maliyetAyarlari() {
  if (!DURUM.yapilandirma.maliyet) DURUM.yapilandirma.maliyet = {};
  const m = DURUM.yapilandirma.maliyet;
  if (!m.poz_fiyatlari) m.poz_fiyatlari = {};
  return m;
}

function maliyetPozlari() {
  const fiyatlar = maliyetAyarlari().poz_fiyatlari;
  const gorulen = [...new Set((DURUM.sonSatirlar || []).map((s) => s.poz))];
  const pozlar = [...new Set([...gorulen, ...Object.keys(fiyatlar)])].sort();
  const tanimlar = {};
  (DURUM.sonSatirlar || []).forEach((s) => {
    if (!tanimlar[s.poz] && s.tanim) tanimlar[s.poz] = s.tanim;
  });
  return pozlar.map((poz) => ({ poz, fiyat: fiyatlar[poz] ?? "", tanim: tanimlar[poz] || "" }));
}

function maliyetFormuYenile() {
  const m = maliyetAyarlari();
  const satirlar = maliyetPozlari().map((p) => `<tr>
    <td class="sol">${esc(p.poz)}</td>
    <td class="sol">${esc(p.tanim)}</td>
    <td><input type="number" step="1" min="0" data-maliyet-fiyat="${esc(p.poz)}"
      value="${p.fiyat === "" ? "" : p.fiyat}" placeholder="fiyat yok"></td>
  </tr>`).join("");

  $("#maliyet-form").innerHTML = `
    <div class="form-satir">
      <label class="alan alan-tam">Maliyet hesabı açık (metraj sonucuna eklenir)
        <span class="anahtar"><input type="checkbox" id="maliyet-aktif" ${m.aktif ? "checked" : ""}><span class="kaydirici"></span></span>
      </label>
    </div>
    <div class="form-satir">
      <label class="alan">Para birimi
        <input type="text" id="maliyet-birim" value="${esc(m.para_birimi || "TL")}">
      </label>
      <label class="alan">KDV (%)
        <input type="number" id="maliyet-kdv" step="1" min="0" value="${esc(m.kdv_oran ?? 20)}">
      </label>
      <label class="alan">Birim fiyat dosyası (yml)
        <input type="text" id="maliyet-fiyatlar" value="${esc(m.fiyatlar_yolu || "")}"
          placeholder="birim_fiyatlar.yml">
      </label>
    </div>
    <div class="bolum-baslik">💰 Poz Birim Fiyatları (TL)</div>
    <div class="tablo-kapsayici">
      <table class="metraj">
        <thead><tr>
          <th class="sol">Poz</th><th class="sol">Tanım</th><th>Birim Fiyat (${esc(m.para_birimi || "TL")})</th>
        </tr></thead>
        <tbody>${satirlar || `<tr><td colspan="3" class="sol">Önce bir metraj çalıştırın; pozlar burada listelenecek.</td></tr>`}</tbody>
      </table>
    </div>
    <div class="form-satir" style="margin-top:12px">
      <button id="maliyet-hesapla" class="birincil">Hesapla &amp; Göster</button>
    </div>
    <p class="maliyet-not">Fiyatlar ORNEKTIR; güncel bakanlık birim fiyatlarını girin.
      "Aktif" açıkken metraj/toplu sonucuna ve Excel'e yaklaşık maliyet eklenir.
      "Birim fiyat dosyası" sunucudan erişilebilen bir yml yoludur
      (ör. <code>birim_fiyatlar.yml</code>); buradaki fiyatlar o dosyayı ezer.</p>`;

  const aktif = $("#maliyet-aktif");
  aktif.addEventListener("change", () => { m.aktif = aktif.checked; });
  $("#maliyet-birim").addEventListener("input", () => { m.para_birimi = $("#maliyet-birim").value; });
  $("#maliyet-fiyatlar").addEventListener("input", () => { m.fiyatlar_yolu = $("#maliyet-fiyatlar").value; });
  $("#maliyet-kdv").addEventListener("input", () => {
    const n = parseFloat($("#maliyet-kdv").value);
    if (Number.isFinite(n)) m.kdv_oran = n;
  });
  $$("[data-maliyet-fiyat]", $("#maliyet-form")).forEach((g) => {
    g.addEventListener("input", () => {
      const n = parseFloat(g.value);
      m.poz_fiyatlari[g.dataset.maliyetFiyat] = Number.isFinite(n) && n > 0 ? n : 0;
    });
  });
  $("#maliyet-hesapla").addEventListener("click", maliyetHesapla);
}

function maliyetHesapla() {
  const alan = $("#maliyet-sonuc");
  const fiyatlar = maliyetAyarlari().poz_fiyatlari || {};
  if (!DURUM.sonSatirlar || !DURUM.sonSatirlar.length) {
    alan.innerHTML = `<div class="hata-kutusu">Önce Metraj veya Toplu sekmesinde bir metraj üretin.</div>`;
    alan.hidden = false;
    return;
  }
  const m = maliyetAyarlari();
  const kalemler = [];
  const fiyatli = new Set();
  DURUM.sonSatirlar.forEach((s) => {
    const fiyat = fiyatlar[s.poz];
    if (fiyat === undefined || fiyat === null || !(fiyat > 0)) return;
    fiyatli.add(s.poz);
    const miktar = s.dusum ? -(s.miktar || 0) : (s.miktar || 0);
    const tutar = miktar * fiyat;
    if (Math.abs(tutar) < 1e-9) return;
    kalemler.push({ poz: s.poz, tanim: s.tanim || "", eleman: s.eleman || "", birim: s.birim || "", miktar, fiyat, tutar, dusum: !!s.dusum });
  });
  const ara = kalemler.reduce((a, k) => a + k.tutar, 0);
  const kdvOran = Number(m.kdv_oran ?? 20);
  const kdv = ara * kdvOran / 100;
  const toplam = ara + kdv;
  const birim = m.para_birimi || "TL";
  const eksik = [...new Set(DURUM.sonSatirlar.map((s) => s.poz))].filter((p) => !fiyatli.has(p)).sort();

  const rows = kalemler.map((k) => `<tr class="${k.dusum ? "dusum" : ""}">
    <td class="sol">${esc(k.poz)}</td>
    <td class="sol">${esc(k.tanim)}</td>
    <td class="sol">${esc(k.eleman)}</td>
    <td>${sayiFormat(k.miktar, 2)} ${esc(k.birim)}</td>
    <td>${sayiFormat(k.fiyat, 2)}</td>
    <td class="vurgulu">${sayiFormat(k.tutar, 2)}</td>
  </tr>`).join("");

  alan.innerHTML = `
    <div class="sonuc-ust"><div class="sonuc-ust-bilgi">
      <h2>Yaklaşık Maliyet <span class="badge badge-kat">${esc(DURUM.sonKaynak)}</span></h2>
      <p>${kalemler.length} kalem poz fiyatlı — ${DURUM.sonSatirlar.length} metraj satırı.</p>
    </div></div>
    <div class="tablo-kapsayici"><table class="metraj">
      <thead><tr>
        <th class="sol">Poz</th><th class="sol">Tanım</th><th class="sol">Eleman</th>
        <th>Miktar</th><th>Birim Fiyat</th><th>Tutar</th>
      </tr></thead>
      <tbody>${rows || `<tr><td colspan="6" class="sol">Hiçbir poz için fiyat girilmedi.</td></tr>`}</tbody>
    </table></div>
    <div class="maliyet-toplam">
      <span>Ara toplam <b>${sayiFormat(ara, 2)}</b></span>
      <span>KDV (%${kdvOran}) <b>${sayiFormat(kdv, 2)}</b></span>
      <span>GENEL TOPLAM <b>${sayiFormat(toplam, 2)} ${esc(birim)}</b></span>
    </div>
    ${eksik.length ? `<div class="uyari-kutu"><div class="uyari-kutu-baslik">Fiyat tanımsız pozlar</div>
      <ul>${eksik.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>` : ""}
    <p class="maliyet-not">Birim fiyatlar ORNEKTIR; kesin bedel için güncel bakanlık birim fiyatlarını girin.</p>`;
  alan.hidden = false;
}

/* ---------------- Baslangic ---------------- */

async function baslangicYukle() {
  try {
    const d = await api("/api/durum");
    $("#surum-alani").textContent = "v" + d.versiyon;
    DURUM.varsayilan = d.varsayilan;
    DURUM.yapilandirma = derinKopya(d.varsayilan);
    hizliFormlariYenile();
    katAlanlariniYenile();
    ayarlarFormuYenile();

    const eksikler = d.bagimliliklar.filter((b) => !b.tamam);
    if (eksikler.length) {
      $("#durum-alani").className = "durum-eksik";
      $("#durum-alani").textContent = eksikler[0].ad;
    }
  } catch (e) {
    bildirim("Sunucuya bağlanılamadı: " + e.message, "hata");
  }
}

function olaylariBagla() {
  $$(".menu-ogesi").forEach((b) => b.addEventListener("click", () => sekmeAc(b.dataset.sekme)));

  birakAlaniYukle($("#metraj-birak"), $("#metraj-dosya"), () => { /* seçim bilgisi bırakma alanında */ });
  birakAlaniYukle($("#pdf-birak"), $("#pdf-dosya"), () => { /* seçim bilgisi bırakma alanında */ });
  birakAlaniYukle($("#esle-birak"), $("#esle-dosya"), () => { /* seçim bilgisi bırakma alanında */ });

  $("#metraj-hesapla").addEventListener("click", metrajCalistir);
  $("#toplu-hesapla").addEventListener("click", topluCalistir);
  $("#toplu-ekle").addEventListener("click", () => topluSatirEkle());
  $("#pdf-incele").addEventListener("click", pdfIncele);
  $("#esle-tara").addEventListener("click", esleTara);
  $("#esle-uygula").addEventListener("click", esleUygula);
  $("#esle-yaml").addEventListener("click", esleYamlIndir);

  $("#ayar-varsayilan").addEventListener("click", ayarlariYenile);
  $("#ayar-indir").addEventListener("click", async () => {
    try {
      indirMetin(await yamlUret(), "hakedis.yml", "application/yaml");
    } catch (e) { bildirim("YAML üretilemedi: " + e.message, "hata"); }
  });
  $("#ayar-yaml-dosya").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const metin = await f.text();
    try {
      DURUM.yapilandirma = await yamlCoz(metin);
      ayarFormlariniYenile();
      bildirim("YAML forma uygulandı.");
    } catch (err) { bildirim("YAML çözülemedi: " + err.message, "hata"); }
    e.target.value = "";
  });

  const gelismis = $("#ayar-gelismis");
  gelismis.addEventListener("change", async () => {
    $("#ayar-yaml-alani").hidden = !gelismis.checked;
    if (gelismis.checked) {
      try { $("#ayar-yaml-metin").value = await yamlUret(); }
      catch (e) { bildirim("YAML üretilemedi: " + e.message, "hata"); }
    }
  });
  $("#ayar-yaml-formdan").addEventListener("click", async () => {
    try { $("#ayar-yaml-metin").value = await yamlUret(); }
    catch (e) { bildirim("YAML üretilemedi: " + e.message, "hata"); }
  });
  $("#ayar-yaml-forma").addEventListener("click", async () => {
    try {
      DURUM.yapilandirma = await yamlCoz($("#ayar-yaml-metin").value);
      ayarFormlariniYenile();
      bildirim("YAML forma uygulandı.");
    } catch (e) { bildirim("YAML çözülemedi: " + e.message, "hata"); }
  });

  katAlanlariniBagla();
}

document.addEventListener("DOMContentLoaded", () => {
  olaylariBagla();
  topluSatirEkle();
  baslangicYukle();
});
