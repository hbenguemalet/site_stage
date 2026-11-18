/* Mes stages — page perso
   Affiche window.STAGES (offres.js, généré par le bot d'offres) comme une boîte de
   réception : chaque offre a un statut (à trier, m'intéresse, postulé, écartée),
   une vérification des 3 critères (rythme, début, missions data) et une note.
   Tout est gardé sur l'appareil (localStorage) ; la page marche aussi sans.
   Aucune dépendance. */
(function () {
  "use strict";

  var DATA = window.STAGES || { meilleures: [], autres: [], liens: [] };
  var CLE = "stages-design:v1";
  var CRITERES = [["lieu", "Lieu qui me convient"], ["dates", "Dates compatibles avec mon année"], ["missions", "Missions en lien avec mon DN MADE"]];
  var AIDES = {
    trier: "Ouvre l'annonce, puis garde-la avec « Je garde » ou écarte-la avec ✕.",
    interesse: "Vérifie les 3 critères dans l'annonce, puis appuie sur « J'ai postulé ».",
    postule: "Tes candidatures, de la plus récente à la plus ancienne.",
    ecarte: "Les offres que tu as écartées. Tu peux en remettre une à trier."
  };
  var VIDES = {
    trier: ["Tout est trié", "Les nouvelles offres apparaîtront ici."],
    interesse: ["Aucune offre gardée pour l'instant", "Dans « À trier », appuie sur « Je garde »."],
    postule: ["Pas encore de candidature", "Dans « Gardées », appuie sur « J'ai postulé »."],
    ecarte: ["Rien d'écarté", ""]
  };

  // ---------- mémoire de l'appareil ----------
  var memo = { statuts: {}, verif: {}, notes: {}, connues: null, derniere: null, refConnues: null, refDate: null };
  try {
    var lu = JSON.parse(localStorage.getItem(CLE) || "null");
    if (lu) memo = Object.assign(memo, lu);
  } catch (e) { /* navigation privée : on repart de zéro */ }
  function sauver() { try { localStorage.setItem(CLE, JSON.stringify(memo)); } catch (e) { /* tant pis */ } }

  // ---------- les offres ----------
  var RX_PUBLIC = /minist|mairie|ville de |r[ée]gion|d[ée]partement|universit|mus[ée]e|th[ée][âa]tre|op[ée]ra|biblioth|fondation|centre (national|culturel|pompidou)|palais|galerie|festival|cin[ée]math|archives|monuments|\bcnap\b|\bcnc\b|\bbnf\b|\bmucem\b|\blouvre\b|mobilier national|manufacture|p[ôo]le emploi|france travail|m[ée]tropole|collectivit/i;
  var RX_ESN = /studio|agence|agency|atelier|design|cr[ée]atif|creative|branding|graphi|print|[ée]dition|editions|motion|architect|maison d|label|collectif|label/i;
  function typeEmployeur(o) {
    if (RX_PUBLIC.test(o.entreprise)) return "public";
    if (RX_ESN.test(o.entreprise)) return "studio";
    return "entreprise";
  }
  function ville(o) {
    if (/lille|roubaix|tourcoing|villeneuve|marcq|croix|lomme|ronchin|wasquehal|lambersart|loos|seclin|madeleine|\b59\b/i.test(o.lieu)) return "lille";
    if (/paris|\b75\b|\b92\b|\b93\b|\b94\b|la d[ée]fense|montreuil|saint-denis|boulogne|issy|levallois|ivry|pantin|clichy/i.test(o.lieu)) return "paris";
    return "ailleurs";
  }
  var offres = [];
  (DATA.meilleures || []).forEach(function (o) { offres.push(Object.assign({ proche: true }, o)); });
  (DATA.autres || []).forEach(function (o) { offres.push(Object.assign({ proche: false }, o)); });
  offres.forEach(function (o) { o.type = typeEmployeur(o); o.ville = ville(o); });

  // ---------- nouveautés depuis la dernière visite ----------
  // Une « visite » commence après 30 min d'absence : recharger la page ne fait pas
  // disparaître les badges « Nouveau » de la visite en cours.
  var maintenant = Date.now();
  if (!memo.derniere || maintenant - Date.parse(memo.derniere) > 30 * 60 * 1000) {
    memo.refConnues = memo.connues;
    memo.refDate = memo.derniere;
  }
  var premiereVisite = !memo.refConnues;
  var connues = {}; (memo.refConnues || []).forEach(function (u) { connues[u] = 1; });
  var nouvelles = {};
  if (!premiereVisite) offres.forEach(function (o) { if (!connues[o.url]) nouvelles[o.url] = 1; });
  var visitePrecedente = memo.refDate;
  memo.connues = offres.map(function (o) { return o.url; });
  memo.derniere = new Date(maintenant).toISOString();
  sauver();

  // ---------- état de l'écran ----------
  var vue = "trier", filtre = { ville: "", type: "", rse: false, q: "" }, voirTout = false;

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function statut(o) { return (memo.statuts[o.url] || {}).s || "trier"; }
  var DIX_JOURS = 10 * 24 * 3600 * 1000;
  function aRelancer(o) { var i = memo.statuts[o.url]; return i && i.s === "postule" && i.d && Date.now() - Date.parse(i.d) > DIX_JOURS; }
  function pluriel(n, mot) { return n + " " + mot + (n > 1 ? "s" : ""); }
  function jour(iso) { return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long" }); }

  function passeFiltres(o) {
    if (filtre.ville && o.ville !== filtre.ville) return false;
    if (filtre.type && o.type !== filtre.type) return false;
    if (filtre.rse && !o.etoile) return false;
    var q = norm(filtre.q);
    return !q || norm(o.titre + " " + o.entreprise + " " + o.lieu).indexOf(q) >= 0;
  }

  // ---------- changer le statut (avec « Annuler ») ----------
  var minuteur = null;
  function changer(o, s, message) {
    var avant = memo.statuts[o.url] ? Object.assign({}, memo.statuts[o.url]) : null;
    if (s === "trier") delete memo.statuts[o.url];
    else memo.statuts[o.url] = { s: s, d: new Date().toISOString() };
    sauver(); afficher();
    $("s-toast-txt").textContent = message;
    $("s-toast").hidden = false;
    $("s-toast-annuler").onclick = function () {
      if (avant) memo.statuts[o.url] = avant; else delete memo.statuts[o.url];
      sauver(); afficher(); $("s-toast").hidden = true;
    };
    clearTimeout(minuteur);
    minuteur = setTimeout(function () { $("s-toast").hidden = true; }, 5000);
  }

  function bouton(cls, txt, fn) {
    var b = el("button", "s-act " + cls, txt); b.type = "button"; b.addEventListener("click", fn); return b;
  }

  // ---------- vérification des 3 critères + note ----------
  function blocVerif(o) {
    var v = memo.verif[o.url] || (memo.verif[o.url] = {});
    var bloc = el("div", "s-verif");
    bloc.appendChild(el("p", "s-verif-titre", "Dans l'annonce, j'ai vérifié :"));
    var alerte = el("p", "s-alerte");
    function majAlerte() {
      var non = CRITERES.filter(function (c) { return v[c[0]] === "non"; }).map(function (c) { return c[1].toLowerCase(); });
      alerte.textContent = non.length ? "Ne colle pas : " + non.join(", ") + ". Tu peux l'écarter." : "";
      alerte.hidden = !non.length;
    }
    CRITERES.forEach(function (c) {
      var ligne = el("div", "s-critere");
      ligne.appendChild(el("span", null, c[1]));
      var tri = el("span", "s-tri"); tri.setAttribute("role", "group"); tri.setAttribute("aria-label", c[1]);
      [["ok", "Oui"], ["non", "Non"]].forEach(function (choix) {
        var b = el("button", null, choix[1]); b.type = "button"; b.dataset.v = choix[0];
        b.setAttribute("aria-pressed", v[c[0]] === choix[0]);
        b.addEventListener("click", function () {
          v[c[0]] = v[c[0]] === choix[0] ? undefined : choix[0];
          tri.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", v[c[0]] === x.dataset.v); });
          sauver(); majAlerte();
        });
        tri.appendChild(b);
      });
      ligne.appendChild(tri);
      bloc.appendChild(ligne);
    });
    majAlerte();
    bloc.appendChild(alerte);
    var note = el("textarea", "s-note");
    note.rows = 1; note.placeholder = "Une note (contact, date limite…)"; note.value = memo.notes[o.url] || "";
    note.setAttribute("aria-label", "Note sur cette offre");
    note.addEventListener("input", function () { memo.notes[o.url] = note.value; sauver(); });
    bloc.appendChild(note);
    return bloc;
  }

  // ---------- une carte ----------
  function carte(o) {
    var s = statut(o);
    var li = el("li", "s-offre" + (nouvelles[o.url] && s === "trier" ? " est-nouvelle" : ""));
    var tete = el("div", "s-tete");
    if (nouvelles[o.url]) tete.appendChild(el("span", "a-chip a-chip--good", "Nouveau"));
    if (o.etoile) tete.appendChild(el("span", "a-chip a-chip--good", "★ Data"));
    tete.appendChild(el("span", "a-chip", { entreprise: "Entreprise", studio: "Studio · Agence", public: "Culture · Public" }[o.type]));
    if (o.salaire) tete.appendChild(el("span", "a-chip", o.salaire));
    if (o.note) tete.appendChild(el("span", "a-chip a-chip--warn", o.note));
    li.appendChild(tete);

    var bloc = el("div");
    var h = el("h2", "s-titre"); var a = el("a", null, o.titre);
    a.href = o.url; a.target = "_blank"; a.rel = "noopener"; h.appendChild(a);
    bloc.appendChild(h);
    bloc.appendChild(el("p", "s-meta", [o.entreprise, o.lieu, o.site ? "via " + o.site : ""].filter(Boolean).join(" · ")));
    if (o.infos && o.infos.length) {
      var inf = el("p", "s-infos");
      o.infos.forEach(function (t) {
        inf.appendChild(el("span", "a-chip" + (/non précis/.test(t) ? " a-chip--warn" : " a-chip--good"), t));
      });
      bloc.appendChild(inf);
    }
    li.appendChild(bloc);

    var info = memo.statuts[o.url];
    if (s === "postule" && info && info.d) {
      li.appendChild(el("p", "s-statut", "✓ Postulé le " + jour(info.d)));
      if (aRelancer(o)) tete.insertBefore(el("span", "a-chip a-chip--warn", "À relancer ?"), tete.firstChild);
    }
    if (s === "postule" && info && !info.d) li.appendChild(el("p", "s-statut", "✓ Postulé"));
    if (s === "interesse" || s === "postule") li.appendChild(blocVerif(o));

    var actions = el("div", "s-actions");
    var voir = el("a", "s-act s-act--voir", "Voir l'annonce ↗");
    voir.href = o.url; voir.target = "_blank"; voir.rel = "noopener";
    actions.appendChild(voir);
    if (s === "trier") {
      actions.appendChild(bouton("s-act--oui", "♥ Je garde", function () { changer(o, "interesse", "Rangée dans « Gardées »"); }));
      actions.appendChild(bouton("s-act--non", "✕", function () { changer(o, "ecarte", "Offre écartée"); }));
      actions.lastChild.setAttribute("aria-label", "Pas pour moi");
    } else if (s === "interesse") {
      actions.appendChild(bouton("s-act--postule", "J'ai postulé", function () { changer(o, "postule", "Bravo ! Rangée dans « Postulé »"); }));
      actions.appendChild(bouton("s-act--non", "✕", function () { changer(o, "ecarte", "Offre écartée"); }));
      actions.lastChild.setAttribute("aria-label", "Finalement pas pour moi");
    } else if (s === "postule") {
      actions.appendChild(bouton("", "Annuler la candidature", function () { changer(o, "interesse", "Remise dans « Gardées »"); }));
    } else {
      actions.appendChild(bouton("", "Remettre à trier", function () { changer(o, "trier", "Remise dans « À trier »"); }));
    }
    li.appendChild(actions);
    return li;
  }

  // ---------- affichage ----------
  function afficher() {
    var compte = { trier: 0, interesse: 0, postule: 0, ecarte: 0 };
    offres.forEach(function (o) { compte[statut(o)]++; });
    Object.keys(compte).forEach(function (k) { $("n-" + k).textContent = compte[k]; });
    bulle(compte);

    var liste = offres.filter(function (o) { return statut(o) === vue && passeFiltres(o); });
    if (vue === "trier") {
      liste.sort(function (a, b) { return (nouvelles[b.url] ? 1 : 0) - (nouvelles[a.url] ? 1 : 0) || (b.proche ? 1 : 0) - (a.proche ? 1 : 0) || (b.score || 0) - (a.score || 0); });
    } else {
      liste.sort(function (a, b) { return String((memo.statuts[b.url] || {}).d).localeCompare(String((memo.statuts[a.url] || {}).d)); });
    }
    var cachees = 0;
    if (vue === "trier" && !voirTout) {
      var visibles = liste.filter(function (o) { return o.proche || nouvelles[o.url]; });
      cachees = liste.length - visibles.length;
      liste = visibles;
    }

    $("s-aide").textContent = AIDES[vue];
    var ol = $("s-liste"); ol.textContent = "";
    if (!liste.length) {
      var vide = el("li", "s-vide");
      var mini = el("img", "s-mini"); mini.src = "bot.svg"; mini.alt = ""; vide.appendChild(mini);
      var filtres = filtre.ville || filtre.type || filtre.rse || filtre.q;
      vide.appendChild(el("strong", null, filtres ? "Aucune offre avec ces filtres" : VIDES[vue][0]));
      vide.appendChild(document.createTextNode(filtres ? "Enlève un filtre pour en voir plus." : VIDES[vue][1]));
      ol.appendChild(vide);
    }
    liste.forEach(function (o) { ol.appendChild(carte(o)); });

    $("s-plus").hidden = !cachees;
    $("s-plus-btn").textContent = "Voir " + cachees + " autre" + (cachees > 1 ? "s" : "") + " offre" + (cachees > 1 ? "s" : "");
  }

  // ---------- en-tête, onglets, filtres ----------
  // La bulle du robot : un seul message, le plus utile du moment.
  function bulle(compte) {
    var relances = offres.filter(aRelancer).length;
    var nouvATrier = offres.filter(function (o) { return nouvelles[o.url] && statut(o) === "trier"; }).length;
    var txt;
    if (!offres.length)
      txt = "Salut ! Je n'ai pas encore trouvé de stage pour toi. Je te préviens dès qu'un arrive.";
    else if (premiereVisite && !compte.interesse && !compte.postule && !compte.ecarte)
      txt = "Salut ! J'ai repéré " + pluriel(offres.length, "stage") + " en design, graphisme, mode et culture, en France et en Europe. Pense à vérifier les dates avant de postuler !";
    else if (nouvATrier)
      txt = pluriel(nouvATrier, "nouveau stage") + " depuis ta visite du " + jour(visitePrecedente) + " ! Ils sont en haut de « À trier ».";
    else if (relances)
      txt = pluriel(relances, "candidature") + " envoyée" + (relances > 1 ? "s" : "") + " il y a plus de 10 jours. Un petit mail de relance ?";
    else if (compte.interesse)
      txt = pluriel(compte.interesse, "offre") + " gardée" + (compte.interesse > 1 ? "s" : "") + " t'attend" + (compte.interesse > 1 ? "ent" : "") + " : vérifie le rythme, le début et les missions.";
    else if (compte.postule)
      txt = "Déjà " + pluriel(compte.postule, "candidature") + ", bravo ! Je te préviens dès qu'un nouveau stage arrive.";
    else if (compte.trier)
      txt = "Encore " + pluriel(compte.trier, "offre") + " à trier. Garde celles qui te plaisent, écarte les autres.";
    else
      txt = "Tout est trié ! Je te préviens dès qu'un nouveau stage arrive.";
    var b = $("s-bulle");
    if (b.textContent !== txt) { b.textContent = txt; b.style.animation = "none"; void b.offsetWidth; b.style.animation = ""; }
  }

  if (DATA.date) $("s-maj").textContent = "Liste mise à jour le " + jour(DATA.date + "T12:00:00Z");

  document.querySelectorAll(".s-onglet").forEach(function (b) {
    b.addEventListener("click", function () {
      vue = b.dataset.vue;
      document.querySelectorAll(".s-onglet").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      afficher();
    });
  });
  function groupe(attr) {
    var boutons = document.querySelectorAll(".s-filtre[data-" + attr + "]");
    boutons.forEach(function (b) {
      b.addEventListener("click", function () {
        filtre[attr] = b.dataset[attr];
        boutons.forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
        afficher();
      });
    });
  }
  groupe("ville"); groupe("type");
  $("f-rse").addEventListener("click", function () { filtre.rse = !filtre.rse; this.setAttribute("aria-pressed", filtre.rse); afficher(); });
  $("s-cherche").addEventListener("input", function (e) { filtre.q = e.target.value; afficher(); });
  $("s-plus-btn").addEventListener("click", function () { voirTout = true; afficher(); });

  (DATA.liens || []).forEach(function (l) {
    var a = el("a", null, l[0]); a.href = l[2]; a.target = "_blank"; a.rel = "noopener";
    a.appendChild(el("small", null, l[1]));
    $("s-liens").appendChild(a);
  });

  afficher();
})();
