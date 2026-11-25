/* Mes stages — page perso
   Affiche window.STAGES (offres.js, généré par le bot d'offres) comme une boîte de
   réception : chaque offre a un statut (à trier, gardée, postulé, écartée), une
   vérification des critères, une note, et un suivi de candidature (relance,
   entretien, réponse). Tout est gardé sur l'appareil (localStorage), exportable.
   Aucune dépendance.

   Le haut du fichier (SITE) est propre à ce site ; le moteur en dessous est le même
   que celui de la page des alternances. */

/* =================== réglages propres à ce site =================== */
var SITE = {
  cle: "stages-design:v1",
  nom: "stage",
  criteres: [["lieu", "Lieu qui me convient"], ["dates", "Dates : avril à août 2027, 16 semaines"], ["missions", "Missions en graphisme ou lignes éditoriales"]],
  villesDynamiques: false,
  typeLabels: { entreprise: "Entreprise", studio: "Studio · Agence", public: "Culture · Public" },
  typeEmployeur: function (o) {
    if (/minist|mairie|ville de |r[ée]gion|d[ée]partement|universit|mus[ée]e|th[ée][âa]tre|op[ée]ra|biblioth|fondation|centre (national|culturel|pompidou)|palais|galerie|festival|cin[ée]math|archives|monuments|\bcnap\b|\bcnc\b|\bbnf\b|\bmucem\b|\blouvre\b|mobilier national|manufacture|p[ôo]le emploi|france travail|m[ée]tropole|collectivit/i.test(o.entreprise)) return "public";
    if (/studio|agence|agency|atelier|design|cr[ée]atif|creative|branding|graphi|print|[ée]dition|editions|motion|architect|maison d|label|collectif|label/i.test(o.entreprise)) return "studio";
    return "entreprise";
  },
  ville: function (o) {
    if (/lille|roubaix|tourcoing|villeneuve|marcq|croix|lomme|ronchin|wasquehal|lambersart|loos|seclin|madeleine|\b59\b/i.test(o.lieu)) return ["lille", "Lille"];
    if (/paris|\b75\b|\b92\b|\b93\b|\b94\b|la d[ée]fense|montreuil|saint-denis|boulogne|issy|levallois|ivry|pantin|clichy/i.test(o.lieu)) return ["paris", "Paris"];
    return ["ailleurs", "Ailleurs · Europe"];
  },
  contrat: null,
  etoile: null,
  actionGardee: null,
  // annonces à l'étranger ou en anglais : lien de traduction
  actionToujours: function (o, el) {
    if (o.ville !== "ailleurs" && !/\b(intern(ship)?|trainee|praktik\w*|pr[aá]cticas|est[aá]gio|tirocinio|stagiair\w*|werkstudent|graphic|designer|assistant|manager)\b/i.test(o.titre)) return null;
    var trad = el("a", "s-act s-act--voir", "Traduire en français");
    trad.href = "https://translate.google.com/translate?sl=auto&tl=fr&u=" + encodeURIComponent(o.url);
    trad.target = "_blank"; trad.rel = "noopener";
    return trad;
  },
  // Note de compatibilité /10 entre chaque offre et le CV de Loréna (graphisme, lignes éditoriales,
  // stage de 16 semaines d'avril à août 2027, à Lille ou ailleurs en France et en Europe).
  compat: {
    seuil: 5,
    contratCible: "stage",
    libCible: "un stage",
    plafondHorsAlternance: 4,                  // un CDI / CDD / alternance ne peut pas dépasser cette note
    plafondSenior: 3.5,                        // un poste confirmé / senior
    plafondHorsData: 3.5,                      // poste hors graphisme / communication visuelle (plafonnée)
    roles: { editorial: 3, graphisme: 3, communication: 2.2, illustration: 2, digital: 1.8, autre: 0.3 },
    roleNoms: { editorial: "Poste en édition et lignes éditoriales", graphisme: "Poste de graphisme",
      communication: "Poste en communication visuelle", illustration: "Poste d'illustration",
      digital: "Poste de design digital", autre: "Poste hors graphisme" },
    lieux: { lille: 1, paris: 0.9, autre: 0.85 },   // ouverte à l'étranger : ailleurs ne pénalise presque pas
    debutCible: { mois: 4, an: 2027 },         // début visé : avril 2027
    libDebut: "ton stage d'avril 2027",
    txtDebutOk: "ça colle avec ton stage",
    txtJunior: "Ouvert aux étudiants",
    domainesProches: ["édition", "culture", "communication", "graphisme"],
    // rôle, contrat et domaines lus dans le titre et l'intitulé de l'offre (le bot n'analyse que la data)
    signaux: function (o) {
      var t = o.titre || "", c = String(o.contrat || ""), tc = (t + " " + c).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(), ent = o.entreprise || "";
      var contrat = /\bstag|intern|stagiaire|trainee|praktik|pr[aá]cticas|est[aá]gio|tirocinio|werkstudent/.test(tc) ? "stage"
        : /alternan|apprenti/.test(tc) ? "alternance" : /\bcdd\b|temporaire|fixed/.test(tc) ? "cdd"
        : /\bcdi\b|permanent|fulltime|full-time/.test(tc) ? "cdi" : "inconnu";
      var role = /[eé]dition|[eé]ditorial|magazine|maquette|mise en page|livre|revue|typograph|publication/i.test(t) ? "editorial"
        : /graphi|graphic|identit[ée] visuelle|print|supports? visuels?|designer/i.test(t) ? "graphisme"
        : /communication|community|r[ée]seaux|social media|contenu|vid[ée]o|motion|montage|photo/i.test(t) ? "communication"
        : /illustr|dessin|artist/i.test(t) ? "illustration"
        : /\bux\b|\bui\b|digital|web design/i.test(t) ? "digital" : "autre";
      var niveau = /senior|confirm|lead|manager|exp[ée]riment/i.test(t) ? "senior" : /junior|d[ée]butant|stagiaire|stage/i.test(t) ? "junior" : "";
      var domaines = [];
      if (/[eé]dition|[eé]ditorial|magazine|livre|revue|presse/i.test(t + " " + ent)) domaines.push("édition");
      if (/culture|mus[ée]e|festival|cin[ée]ma|th[ée][âa]tre|galerie|patrimoine|biblioth|mucem|louvre/i.test(t + " " + ent)) domaines.push("culture");
      if (/communication|marketing|r[ée]seaux/i.test(t)) domaines.push("communication");
      if (/graphi|design/i.test(t)) domaines.push("graphisme");
      return { contrat: contrat, role: role, niveau: niveau, domaines: domaines };
    }
  },
  objectifDefaut: 3,
  textes: {
    bonjourCompat: function (n, k) { return "Salut ! J'ai repéré " + n + " offres en graphisme et culture, dont " + k + " stage" + (k > 1 ? "s" : "") + " pour ton CV. Je les ai toutes notées sur 10 d'après ton profil : les plus compatibles sont en haut. Touche une note pour voir pourquoi."; },
    des: "stages", nouv: "nouveau stage", nouvP: "nouveaux stages", f: false,
    bonjour: function (n) { return "Salut ! J'ai repéré " + n + " en design, graphisme, mode et culture, en France et en Europe. Pense à vérifier les dates avant de postuler !"; },
    aucune: "Salut ! Je n'ai pas encore trouvé de stage pour toi. Je te préviens dès qu'un arrive.",
    gardees: "vérifie le lieu, les dates et les missions.",
    relanceObjet: "Candidature de stage"
  }
};

/* =================== moteur (identique sur les deux sites) =================== */
(function () {
  "use strict";

  var DATA = window.STAGES || { meilleures: [], autres: [], liens: [] };
  var T = SITE.textes;
  var JOUR = 24 * 3600 * 1000, DIX_JOURS = 10 * JOUR;
  var AIDES = {
    trier: "Ouvre l'annonce, puis garde-la avec « Je garde » ou écarte-la avec ✕. Sur téléphone : glisse vers la droite pour garder, vers la gauche pour écarter.",
    interesse: "Vérifie les critères dans l'annonce, puis appuie sur « J'ai postulé ».",
    postule: "Tes candidatures, de la plus récente à la plus ancienne. Note chaque étape : relance, entretien, réponse.",
    ecarte: "Les offres que tu as écartées. Tu peux en remettre une à trier."
  };
  var VIDES = {
    trier: ["Tout est trié", "Les nouvelles offres apparaîtront ici."],
    interesse: ["Aucune offre gardée pour l'instant", "Dans « À trier », appuie sur « Je garde »."],
    postule: ["Pas encore de candidature", "Dans « Gardées », appuie sur « J'ai postulé »."],
    ecarte: ["Rien d'écarté", ""]
  };

  // ---------- petits outils ----------
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function pluriel(n, mot) { return n + " " + mot + (n > 1 ? "s" : ""); }
  function jour(iso) { return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long" }); }
  function accord(n, m, f) { return n > 1 ? (f ? m + "es" : m + "s") : (f ? m + "e" : m); }
  var calme = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- mémoire de l'appareil ----------
  var memo = { statuts: {}, verif: {}, notes: {}, fiches: {}, vues: {}, prefs: {}, connues: null, derniere: null, refConnues: null, refDate: null };
  try {
    var lu = JSON.parse(localStorage.getItem(SITE.cle) || "null");
    if (lu) memo = Object.assign(memo, lu);
  } catch (e) { /* navigation privée : on repart de zéro */ }
  function sauver() { try { localStorage.setItem(SITE.cle, JSON.stringify(memo)); } catch (e) { /* tant pis */ } }
  var prefs = memo.prefs;
  if (!prefs.objectif) prefs.objectif = SITE.objectifDefaut;
  if (!prefs.tri) prefs.tri = "pertinence";
  if (SITE.compat && !prefs.triCompat) { prefs.tri = "compat"; prefs.triCompat = 1; }   // une fois : la note devient le tri par défaut

  // ---------- les offres ----------
  var NOMS_VILLES = {};
  function preparer(o) {
    o.type = SITE.typeEmployeur(o);
    var v = SITE.ville(o);
    o.ville = v[0] || norm(v[1]);
    NOMS_VILLES[o.ville] = v[1];
    if (SITE.contrat) o.contrat = SITE.contrat(o);
    return o;
  }
  var offres = [], parUrl = {};
  (DATA.meilleures || []).forEach(function (o) { offres.push(Object.assign({ proche: true }, o)); });
  (DATA.autres || []).forEach(function (o) { offres.push(Object.assign({ proche: false }, o)); });
  offres.forEach(function (o) { preparer(o); parUrl[o.url] = o; });

  // Une fiche courte de chaque offre suivie est gardée : quand le bot retire une
  // annonce de sa liste, la candidature reste visible (avec « Plus en ligne »).
  var CHAMPS_FICHE = ["titre", "entreprise", "lieu", "url", "contrat", "salaire", "site", "etoile", "infos", "premiere", "signaux", "outils"];
  function ficher(o) {
    var f = {}; CHAMPS_FICHE.forEach(function (k) { if (o[k] != null) f[k] = o[k]; });
    memo.fiches[o.url] = f;
  }
  Object.keys(memo.statuts).forEach(function (u) {
    if (parUrl[u]) ficher(parUrl[u]);
    else if (memo.fiches[u] && memo.statuts[u].s !== "ecarte") {
      var o = preparer(Object.assign({ proche: true, disparue: true }, memo.fiches[u]));
      offres.push(o); parUrl[u] = o;
    }
  });
  Object.keys(memo.fiches).forEach(function (u) { if (!memo.statuts[u]) delete memo.fiches[u]; });

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
  if (!premiereVisite) offres.forEach(function (o) { if (!o.disparue && !connues[o.url]) nouvelles[o.url] = 1; });
  var visitePrecedente = memo.refDate;
  memo.connues = offres.filter(function (o) { return !o.disparue; }).map(function (o) { return o.url; });
  memo.derniere = new Date(maintenant).toISOString();
  sauver();

  // ---------- état de l'écran ----------
  var vue = "trier", filtre = { ville: "", type: "", contrat: "", rse: false, q: "" }, voirTout = false;
  var curseur = -1; // carte choisie au clavier

  function info(o) { return memo.statuts[o.url] || {}; }

  // ---------- compétences demandées vs avancée du bootcamp ----------
  var BOOT = null;
  var OUTILS_TITRE = [["SQL", /\bsql\b/i], ["Python", /python/i], ["Power BI", /power ?bi/i], ["Excel", /excel/i], ["DAX", /\bdax\b/i],
    ["dbt", /\bdbt\b/i], ["Docker", /docker/i], ["Airflow", /airflow/i], ["BigQuery", /bigquery/i], ["ETL", /\betl\b/i],
    ["Tableau", /tableau software/i], ["Snowflake", /snowflake/i], ["Spark", /\bspark\b/i], ["Databricks", /databricks/i]];
  function outilsOffre(o) {
    if (o.outils) return o.outils;
    return OUTILS_TITRE.filter(function (x) { return x[1].test(o.titre || ""); }).map(function (x) { return x[0]; });
  }
  // état d'un outil : acquis / en cours / à venir / hors (pas au programme du bootcamp)
  function etatOutil(nom) {
    var c = SITE.bootcamp && SITE.bootcamp.outils[nom];
    if (c === "acquis") return { etat: "acquis", pct: 100 };
    if (!c) return { etat: "hors", pct: 0 };
    var comp = BOOT && BOOT.competences.filter(function (x) { return x.nom === c; })[0];
    if (!comp) return { etat: "à venir", pct: 0, comp: c };
    return { etat: comp.etat === "fait" ? "acquis" : comp.etat, pct: comp.pct, comp: c };
  }
  // ---------- note de compatibilité /10 ----------
  var MOIS_NUM = { janvier: 1, fevrier: 2, mars: 3, avril: 4, mai: 5, juin: 6, juillet: 7, aout: 8, septembre: 9, octobre: 10, novembre: 11, decembre: 12,
    january: 1, february: 2, march: 3, april: 4, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12 };
  var NOMS_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  var RX_MOIS = /(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|january|february|march|april|may|june|july|august|september|october|november|december)\s*(20\d\d)/;
  function debutOffre(o) {
    var txt = norm((o.infos || []).filter(function (x) { return /^D[ée]but/.test(x); }).join(" ") + " " + (o.titre || ""));
    var m = txt.match(RX_MOIS);
    if (m) return { mois: MOIS_NUM[m[1]] || 5, an: +m[2] };
    if ((m = txt.match(/rentree\s*(20\d\d)/))) return { mois: 9, an: +m[1] };
    if ((m = txt.match(/debut\s*:\s*(20\d\d)/))) return { mois: 0, an: +m[1] };
    return null;
  }
  // signaux que le bot publie ; secours simple si la page est plus récente que offres.js
  function signauxOffre(o) {
    if (SITE.compat && SITE.compat.signaux) return SITE.compat.signaux(o);
    if (o.signaux) return o.signaux;
    var c = String(o.contrat || "").toLowerCase();
    return { contrat: /alternan|apprenti/.test(c + " " + norm(o.titre)) ? "alternance" : /cdd/.test(c) ? "cdd" : "cdi", role: "data",
      niveau: /senior|confirm|lead|manager|exp[ée]riment/i.test(o.titre || "") ? "senior" : "", domaines: [] };
  }
  function fmtNote(n) { return n.toLocaleString("fr-FR", { minimumFractionDigits: 0, maximumFractionDigits: 1 }); }
  var MAITRISE = { acquis: 1, "en cours": 0.5, "à venir": 0.12, hors: 0 };
  function evaluerCompat(o) {
    var C = SITE.compat; if (!C) return null;
    var sg = signauxOffre(o), r = [], pts = 0, plafond = 10, plafondRaison = "";
    function raison(signe, t) { r.push({ s: signe, t: t }); }

    // contrat (3)
    var cible = C.contratCible || "alternance", alt = sg.contrat === cible;
    if (alt) { pts += 3; raison(1, "Type de contrat recherché : " + C.libCible); }
    else if (sg.contrat === "inconnu") { pts += 1.5; raison(0, "Type de contrat non précisé"); }
    else {
      pts += 0.4; plafond = C.plafondHorsAlternance;
      plafondRaison = (sg.contrat || "cdi").toUpperCase() + " : tu cherches " + C.libCible + " (plafonné à " + C.plafondHorsAlternance + "/10)";
      raison(-1, (sg.contrat === "stage" ? "Stage" : sg.contrat.toUpperCase()) + " : pas " + C.libCible);
    }
    // poste (3)
    var rp = C.roles[sg.role] != null ? C.roles[sg.role] : 0.3;
    pts += rp;
    if (rp >= 2.5) raison(1, C.roleNoms[sg.role] + " : ton objectif");
    else if (rp >= 1.2) raison(0, C.roleNoms[sg.role] + " : proche de ton objectif");
    else {
      raison(-1, C.roleNoms[sg.role] + " : éloigné de ton objectif");
      if (rp < 0.5 && C.plafondHorsData < plafond) { plafond = C.plafondHorsData; plafondRaison = plafondRaison || "Poste hors data (plafonné à " + C.plafondHorsData + "/10)"; }
    }
    // niveau (1)
    if (sg.niveau === "senior") {
      pts += 0; plafond = Math.min(plafond, C.plafondSenior);
      raison(-1, "Poste confirmé / senior" + (sg.annees ? " (" + sg.annees + " ans d'expérience demandés)" : ""));
      plafondRaison = plafondRaison || "Poste senior (plafonné à " + C.plafondSenior + "/10)";
    } else if (sg.niveau === "junior" || alt) { pts += 1; raison(1, C.txtJunior || "Accessible à un profil junior"); }
    else { pts += 0.6; raison(0, "Niveau d'expérience non précisé"); }
    // outils (2) : maîtrise actuelle (Excel…) + avancée du bootcamp
    var outils = outilsOffre(o);
    if (!SITE.bootcamp) { pts += 1.2; }
    else if (outils.length) {
      var tot = 0, ok = [], cours = [], non = [];
      outils.forEach(function (n) {
        var e = etatOutil(n);
        tot += e.etat === "en cours" ? 0.45 + 0.4 * (e.pct / 100) : MAITRISE[e.etat];
        (e.etat === "acquis" ? ok : e.etat === "en cours" ? cours : non).push(n);
      });
      pts += 2 * tot / outils.length;
      if (ok.length) raison(1, "Tu maîtrises : " + ok.join(", "));
      if (cours.length) raison(0, "Bootcamp en cours : " + cours.join(", "));
      if (non.length) raison(-1, "Pas encore vu : " + non.join(", "));
    } else { pts += 0.9; raison(0, "Outils non précisés dans l'annonce"); }
    // lieu (1)
    var lv = o.ville === "lille" ? "lille" : o.ville === "paris" ? "paris" : "autre";
    pts += C.lieux[lv];
    raison(lv === "lille" ? 1 : 0, lv === "lille" ? "Lille : à côté de chez elle" : lv === "paris" ? "Paris : déménagement à prévoir" : "Ailleurs (France ou étranger) : ouverte à la mobilité");
    // début
    var d = debutOffre(o);
    if (d && C.debutCible) {
      var ecart = (d.an * 12 + (d.mois || C.debutCible.mois)) - (C.debutCible.an * 12 + C.debutCible.mois);
      var quand = (d.mois ? NOMS_MOIS[d.mois] + " " : "") + d.an;
      if (ecart < -2) { pts -= 2; raison(-1, "Début en " + quand + " : trop tôt pour " + (C.libDebut || "ta rentrée de " + NOMS_MOIS[C.debutCible.mois] + " " + C.debutCible.an)); }
      else if (ecart <= 2) { pts += 0.5; raison(1, "Début en " + quand + " : " + (C.txtDebutOk || "ça colle avec ta rentrée")); }
      else { pts -= 0.5; raison(-1, "Début en " + quand + " : plus tard que prévu"); }
    }
    // domaine
    var proche = (sg.domaines || []).filter(function (x) { return C.domainesProches.indexOf(x) >= 0; });
    if (proche.length) { pts += 0.5; raison(1, "Domaine proche de ton expérience (" + proche.join(", ") + ")"); }

    var brute = Math.max(0, Math.min(10, pts));
    var note = Math.round(Math.min(brute, plafond) * 2) / 2;
    if (plafondRaison && brute > plafond) raison(-1, plafondRaison);
    var bande = note >= 8 ? "top" : note >= 6.5 ? "bon" : note >= C.seuil ? "moyen" : "bas";
    return { note: note, brute: brute, bande: bande, raisons: r };
  }
  function compat(o) { return o._c || (o._c = evaluerCompat(o)); }
  function compatibilite(o) { var c = compat(o); return c ? c.note : 0; }
  function compatFine(o) { var c = compat(o); return c ? c.note + c.brute / 100 : 0; }   // départage les offres plafonnées
  function blocCompetences(o) {
    var l = outilsOffre(o);
    if (!SITE.bootcamp || !l.length) return null;
    var p = el("p", "s-skills");
    p.appendChild(el("span", "s-skills-titre", "Demandé :"));
    var noms = { acquis: "acquis", "en cours": "en cours", "à venir": "à venir", hors: "hors bootcamp" };
    l.forEach(function (n) {
      var e = etatOutil(n);
      var c = el("span", "s-sk s-sk--" + (e.etat === "en cours" ? "cours" : e.etat === "à venir" ? "venir" : e.etat), n);
      c.title = n + " : " + noms[e.etat] + (e.etat === "en cours" ? " (" + e.pct + " % de « " + e.comp + " » dans le bootcamp)" : "");
      p.appendChild(c);
    });
    return p;
  }
  function statut(o) { return info(o).s || "trier"; }
  function aRelancer(o) {
    var i = info(o);
    if (i.s !== "postule" || i.reponse || i.entretien || !i.d) return false;
    return Date.now() - Date.parse(i.relance || i.d) > DIX_JOURS;
  }
  function age(o) {
    if (!o.premiere) return null;
    var j = Math.floor((Date.now() - Date.parse(o.premiere)) / JOUR);
    return j <= 0 ? "aujourd'hui" : j === 1 ? "hier" : "il y a " + j + " j";
  }

  function passeFiltres(o) {
    if (filtre.ville && o.ville !== filtre.ville) return false;
    if (filtre.type && o.type !== filtre.type) return false;
    if (filtre.contrat && o.contrat !== filtre.contrat) return false;
    if (filtre.rse && !o.etoile) return false;
    var q = norm(filtre.q);
    return !q || norm(o.titre + " " + o.entreprise + " " + o.lieu + " " + (memo.notes[o.url] || "")).indexOf(q) >= 0;
  }

  // ---------- retour visuel ----------
  var minuteur = null;
  function toast(message, annuler) {
    $("s-toast-txt").textContent = message;
    $("s-toast").hidden = false;
    $("s-toast-annuler").hidden = !annuler;
    $("s-toast-annuler").onclick = function () { annuler(); $("s-toast").hidden = true; };
    clearTimeout(minuteur);
    minuteur = setTimeout(function () { $("s-toast").hidden = true; }, 5000);
  }
  function confettis(depuis) {
    if (calme) return;
    var r = depuis ? depuis.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 };
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    var couleurs = ["var(--a-accent)", "var(--a-accent-soft)", "#f5b942", "#ef6f6c", "#5aa9e6", "#8fd18f"];
    for (var i = 0; i < 28; i++) {
      var c = el("i", "s-confetti");
      var a = Math.random() * Math.PI * 2, d = 60 + Math.random() * 110;
      c.style.left = x + "px"; c.style.top = y + "px";
      c.style.background = couleurs[i % couleurs.length];
      c.style.setProperty("--dx", Math.cos(a) * d + "px");
      c.style.setProperty("--dy", Math.sin(a) * d - 60 + "px");
      c.style.setProperty("--r", (Math.random() * 720 - 360) + "deg");
      document.body.appendChild(c);
      setTimeout(function (n) { n.remove(); }.bind(null, c), 1100);
    }
  }

  // ---------- changer le statut (avec « Annuler ») ----------
  // sens : "droite" / "gauche" = la carte glisse hors de la liste avant de partir
  function changer(o, s, message, carteEl, sens) {
    var avant = memo.statuts[o.url] ? Object.assign({}, memo.statuts[o.url]) : null;
    function appliquer() {
      if (s === "trier") delete memo.statuts[o.url];
      else memo.statuts[o.url] = { s: s, d: new Date().toISOString() };
      if (s !== "trier") ficher(o);
      sauver(); afficher();
      toast(message, function () {
        if (avant) memo.statuts[o.url] = avant; else delete memo.statuts[o.url];
        sauver(); afficher();
      });
    }
    if (carteEl && !calme) {
      carteEl.classList.add("sort-" + (sens || "droite"));
      setTimeout(appliquer, 230);
    } else appliquer();
  }
  // étapes d'une candidature : relance, entretien, réponse
  function etape(o, cle, valeur, message) {
    var i = memo.statuts[o.url]; if (!i) return;
    var avant = Object.assign({}, i);
    if (i[cle] && valeur === undefined) delete i[cle];
    else i[cle] = valeur === undefined ? new Date().toISOString() : valeur;
    if (cle === "reponse") i.reponseD = new Date().toISOString();
    sauver(); afficher();
    toast(message, function () { memo.statuts[o.url] = avant; sauver(); afficher(); });
  }

  function bouton(cls, txt, fn, aria) {
    var b = el("button", "s-act " + cls, txt); b.type = "button"; b.addEventListener("click", fn);
    if (aria) b.setAttribute("aria-label", aria);
    return b;
  }

  // ---------- vérification des critères + note ----------
  function blocVerif(o) {
    var v = memo.verif[o.url] || (memo.verif[o.url] = {});
    var bloc = el("div", "s-verif");
    var titre = el("p", "s-verif-titre", "Dans l'annonce, j'ai vérifié :");
    var jauge = el("span", "s-jauge");
    titre.appendChild(jauge);
    bloc.appendChild(titre);
    var alerte = el("p", "s-alerte");
    function majAlerte() {
      var non = SITE.criteres.filter(function (c) { return v[c[0]] === "non"; }).map(function (c) { return c[1].toLowerCase(); });
      var oui = SITE.criteres.filter(function (c) { return v[c[0]] === "ok"; }).length;
      alerte.textContent = non.length ? "Ne colle pas : " + non.join(", ") + ". Tu peux l'écarter." : "";
      alerte.hidden = !non.length;
      jauge.textContent = oui + " / " + SITE.criteres.length;
      jauge.className = "s-jauge" + (oui === SITE.criteres.length ? " est-ok" : "");
    }
    SITE.criteres.forEach(function (c) {
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

  // ---------- suivi d'une candidature ----------
  function rappelICS(o) {
    var i = info(o);
    var base = Date.parse(i.relance || i.d) || Date.now();
    var d = new Date(base + DIX_JOURS);
    function f(x) { return x.toISOString().slice(0, 10).replace(/-/g, ""); }
    var ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//mes-offres//FR", "BEGIN:VEVENT",
      "UID:" + Date.now() + "@mes-offres", "DTSTAMP:" + new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z",
      "DTSTART;VALUE=DATE:" + f(d), "DTEND;VALUE=DATE:" + f(new Date(d.getTime() + JOUR)),
      "SUMMARY:Relancer " + (o.entreprise || "la candidature").replace(/[,;\n]/g, " "),
      "DESCRIPTION:" + (o.titre + " — " + o.url).replace(/[,;]/g, " ").replace(/\n/g, " "),
      "BEGIN:VALARM", "TRIGGER:PT9H", "ACTION:DISPLAY", "DESCRIPTION:Relance", "END:VALARM",
      "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    telecharger("relance-" + norm(o.entreprise || "offre").replace(/[^a-z0-9]+/g, "-") + ".ics", ics, "text/calendar");
  }
  function mailRelance(o) {
    var i = info(o);
    var corps = "Bonjour,\n\nJe me permets de revenir vers vous au sujet de ma candidature au poste « " + o.titre + " »"
      + (i.d ? ", envoyée le " + jour(i.d) : "") + ". Le poste m'intéresse toujours beaucoup et je reste disponible pour un échange "
      + "si mon profil retient votre attention.\n\nBien cordialement,\n";
    return "mailto:?subject=" + encodeURIComponent("Relance — " + T.relanceObjet + " · " + o.titre) + "&body=" + encodeURIComponent(corps);
  }
  function blocSuivi(o, li) {
    var i = info(o);
    var bloc = el("div", "s-suivi-cand");
    var etapes = [["d", "Postulé"], ["relance", "Relancé"], ["entretien", "Entretien"], ["reponse", i.reponse === "non" ? "Refus" : "Réponse"]];
    var frise = el("ol", "s-frise");
    etapes.forEach(function (e) {
      var fait = !!i[e[0]];
      var pas = el("li", "s-pas" + (fait ? " est-fait" : "") + (e[0] === "reponse" && i.reponse ? (i.reponse === "oui" ? " est-oui" : " est-non") : ""));
      pas.appendChild(el("span", "s-pas-pt"));
      pas.appendChild(el("span", "s-pas-nom", e[1]));
      var date = e[0] === "reponse" ? i.reponseD : i[e[0]];
      if (fait && date) pas.appendChild(el("span", "s-pas-date", new Date(date).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })));
      frise.appendChild(pas);
    });
    bloc.appendChild(frise);

    var acts = el("div", "s-mini-acts");
    if (!i.reponse) {
      acts.appendChild(bouton("s-act--mini" + (i.relance ? " est-on" : ""), i.relance ? "✓ Relancé" : "J'ai relancé", function () { etape(o, "relance", undefined, i.relance ? "Relance retirée" : "Relance notée. Prochain rappel dans 10 jours."); }));
      acts.appendChild(bouton("s-act--mini" + (i.entretien ? " est-on" : ""), i.entretien ? "✓ Entretien" : "Entretien décroché", function (e) {
        var avait = i.entretien;
        etape(o, "entretien", undefined, avait ? "Entretien retiré" : "Un entretien, bravo ! Prépare-toi bien.");
        if (!avait) confettis(e.target);
      }));
      acts.appendChild(bouton("s-act--mini s-act--oui", "Pris·e !", function (e) { etape(o, "reponse", "oui", "Félicitations !!"); confettis(e.target); confettis(li); }));
      acts.appendChild(bouton("s-act--mini s-act--non", "Refus", function () { etape(o, "reponse", "non", "Dommage. Ce n'est que partie remise."); }));
    } else {
      acts.appendChild(bouton("s-act--mini", "Effacer la réponse", function () { var x = memo.statuts[o.url]; delete x.reponseD; etape(o, "reponse", undefined, "Réponse effacée"); }));
    }
    var mail = el("a", "s-act s-act--mini", "✉ Mail de relance"); mail.href = mailRelance(o);
    acts.appendChild(mail);
    if (!i.reponse) acts.appendChild(bouton("s-act--mini", "📅 Rappel agenda", function () { rappelICS(o); toast("Rappel de relance téléchargé : ouvre-le pour l'ajouter à ton agenda."); }));
    bloc.appendChild(acts);
    return bloc;
  }

  // ---------- surligner la recherche ----------
  function surligner(parent, texte) {
    var q = norm(filtre.q).trim();
    if (!q) { parent.textContent = texte; return; }
    // index du texte normalisé → index du texte d'origine (les accents se décomposent)
    var n = "", carte = [];
    for (var i = 0; i < texte.length; i++) {
      var c = norm(texte[i]);
      for (var k = 0; k < c.length; k++) { n += c[k]; carte.push(i); }
    }
    var pos = 0, idx;
    parent.textContent = "";
    while ((idx = n.indexOf(q, pos)) >= 0) {
      var a = carte[idx], b = carte[idx + q.length - 1] + 1, debut = carte[pos] != null ? carte[pos] : texte.length;
      if (a > debut) parent.appendChild(document.createTextNode(texte.slice(debut, a)));
      parent.appendChild(el("mark", null, texte.slice(a, b)));
      pos = idx + q.length;
    }
    var reste = carte[pos] != null ? carte[pos] : texte.length;
    if (reste < texte.length) parent.appendChild(document.createTextNode(texte.slice(reste)));
  }

  // ---------- une carte ----------
  function carte(o, rang) {
    var s = statut(o), i = info(o);
    var li = el("li", "s-offre" + (nouvelles[o.url] && s === "trier" ? " est-nouvelle" : "") + (o.disparue ? " est-disparue" : "") + (i.reponse === "oui" ? " est-gagnee" : ""));
    li.tabIndex = -1;
    li.dataset.url = o.url;
    if (!calme) li.style.animationDelay = Math.min(rang, 8) * 35 + "ms";
    var tete = el("div", "s-tete");
    if (aRelancer(o)) tete.appendChild(el("span", "a-chip a-chip--warn", "À relancer ?"));
    if (nouvelles[o.url]) tete.appendChild(el("span", "a-chip a-chip--good", "Nouveau"));
    if (o.disparue) tete.appendChild(el("span", "a-chip a-chip--warn", "Plus en ligne"));
    if (SITE.contrat && o.contrat) tete.appendChild(el("span", "a-chip", SITE.contratLabels[o.contrat] || o.contrat));
    if (o.etoile && SITE.etoile) tete.appendChild(el("span", "a-chip a-chip--good", SITE.etoile));
    tete.appendChild(el("span", "a-chip", SITE.typeLabels[o.type]));
    if (o.salaire) tete.appendChild(el("span", "a-chip", o.salaire));
    if (o.note) tete.appendChild(el("span", "a-chip a-chip--warn", o.note));
    var ag = age(o);
    if (ag && s === "trier") tete.appendChild(el("span", "s-age", "repérée " + ag));
    if (memo.vues[o.url]) tete.appendChild(el("span", "s-vue", "● déjà ouverte"));
    var cp = compat(o), pq = null;
    if (cp) {
      var badge = el("button", "s-compat s-compat--" + cp.bande); badge.type = "button";
      badge.style.setProperty("--p", cp.note * 10);
      badge.appendChild(el("b", null, fmtNote(cp.note))); badge.appendChild(el("small", null, "/10"));
      badge.setAttribute("aria-label", "Compatibilité avec ton profil : " + fmtNote(cp.note) + " sur 10. Voir pourquoi.");
      badge.setAttribute("aria-expanded", "false");
      badge.title = "Compatibilité avec ton profil";
      tete.appendChild(badge);
      pq = el("div", "s-pq"); pq.hidden = true;
      pq.appendChild(el("p", "s-pq-t", "Pourquoi " + fmtNote(cp.note) + " / 10 ?"));
      var ul = el("ul");
      cp.raisons.forEach(function (x) { ul.appendChild(el("li", "s-pq--" + (x.s > 0 ? "ok" : x.s < 0 ? "non" : "mid"), x.t)); });
      pq.appendChild(ul);
      badge.addEventListener("click", function () { pq.hidden = !pq.hidden; badge.setAttribute("aria-expanded", String(!pq.hidden)); });
    }
    li.appendChild(tete);

    var bloc = el("div");
    var h = el("h2", "s-titre"); var a = el("a");
    surligner(a, o.titre);
    a.href = o.url; a.target = "_blank"; a.rel = "noopener"; h.appendChild(a);
    bloc.appendChild(h);
    var meta = el("p", "s-meta");
    surligner(meta, [o.entreprise, o.lieu, o.site ? "via " + o.site : ""].filter(Boolean).join(" · "));
    bloc.appendChild(meta);
    if (o.infos && o.infos.length) {
      var inf = el("p", "s-infos");
      o.infos.forEach(function (t) {
        inf.appendChild(el("span", "a-chip" + (/non précis/.test(t) ? " a-chip--warn" : " a-chip--good"), t));
      });
      bloc.appendChild(inf);
    }
    var comp = blocCompetences(o);
    if (comp) bloc.appendChild(comp);
    li.appendChild(bloc);
    if (pq) li.appendChild(pq);

    if (s === "postule") li.appendChild(blocSuivi(o, li));
    if (s === "interesse" || s === "postule") li.appendChild(blocVerif(o));

    var actions = el("div", "s-actions");
    var voir = el("a", "s-act s-act--voir", "Voir l'annonce ↗");
    voir.href = o.url; voir.target = "_blank"; voir.rel = "noopener";
    actions.appendChild(voir);
    if (SITE.actionToujours) { var t = SITE.actionToujours(o, el); if (t) actions.appendChild(t); }
    if (s === "trier") {
      actions.appendChild(bouton("s-act--oui", "♥ Je garde", function () { changer(o, "interesse", "Rangée dans « Gardées »", li, "droite"); }));
      actions.appendChild(bouton("s-act--non", "✕", function () { changer(o, "ecarte", "Offre écartée", li, "gauche"); }, "Pas pour moi"));
    } else if (s === "interesse") {
      if (SITE.actionGardee) actions.appendChild(SITE.actionGardee(o, el));
      actions.appendChild(bouton("s-act--postule", "J'ai postulé", function (e) { confettis(e.target); changer(o, "postule", "Bravo ! Rangée dans « Postulé »", li, "droite"); }));
      actions.appendChild(bouton("s-act--non", "✕", function () { changer(o, "ecarte", "Offre écartée", li, "gauche"); }, "Finalement pas pour moi"));
    } else if (s === "postule") {
      actions.appendChild(bouton("", "Annuler la candidature", function () { changer(o, "interesse", "Remise dans « Gardées »", li, "gauche"); }));
    } else {
      actions.appendChild(bouton("", "Remettre à trier", function () { changer(o, "trier", "Remise dans « À trier »", li, "droite"); }));
    }
    li.appendChild(actions);
    li.querySelectorAll('a[href^="http"]').forEach(function (x) {
      if (x.href === o.url) x.addEventListener("click", function () { memo.vues[o.url] = 1; sauver(); });
    });
    if (s === "trier") glisser(li, o);
    return li;
  }

  // ---------- glisser au doigt (À trier) ----------
  function glisser(li, o) {
    var x0 = null, y0 = 0, dx = 0, actif = false;
    li.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "touch" || e.target.closest("button, a, textarea")) return;
      x0 = e.clientX; y0 = e.clientY; dx = 0; actif = false;
    });
    li.addEventListener("pointermove", function (e) {
      if (x0 == null) return;
      dx = e.clientX - x0;
      if (!actif && Math.abs(e.clientY - y0) > 14 && Math.abs(dx) < 14) { x0 = null; return; }
      if (!actif && Math.abs(dx) > 14) { actif = true; li.setPointerCapture(e.pointerId); li.classList.add("est-glisse"); }
      if (actif) {
        li.style.transform = "translateX(" + dx + "px) rotate(" + dx / 40 + "deg)";
        li.dataset.glisse = dx > 50 ? "oui" : dx < -50 ? "non" : "";
      }
    });
    function fin() {
      if (x0 == null) return;
      x0 = null;
      li.classList.remove("est-glisse");
      if (actif && Math.abs(dx) > 90) {
        if (dx > 0) changer(o, "interesse", "Rangée dans « Gardées »", li, "droite");
        else changer(o, "ecarte", "Offre écartée", li, "gauche");
      } else { li.style.transform = ""; li.dataset.glisse = ""; }
      actif = false;
    }
    li.addEventListener("pointerup", fin);
    li.addEventListener("pointercancel", fin);
  }

  // ---------- tableau de bord ----------
  function lundi(t) { var d = new Date(t); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (d.getDay() + 6) % 7); return d.getTime(); }
  function suivi(compte) {
    var zone = $("s-suivi"); if (!zone) return;
    var post = Object.keys(memo.statuts).map(function (u) { return memo.statuts[u]; }).filter(function (i) { return i.s === "postule"; });
    var cetteSemaine = lundi(Date.now());
    var semaine = post.filter(function (i) { return i.d && Date.parse(i.d) >= cetteSemaine; }).length;
    var entretiens = post.filter(function (i) { return i.entretien; }).length;
    var oui = post.filter(function (i) { return i.reponse === "oui"; }).length;
    var obj = prefs.objectif;

    // anneau de l'objectif de la semaine
    var p = Math.min(1, semaine / obj), R = 34, C = 2 * Math.PI * R;
    $("s-anneau-arc").style.strokeDasharray = C;
    $("s-anneau-arc").style.strokeDashoffset = C * (1 - p);
    $("s-anneau-n").textContent = semaine;
    $("s-anneau-obj").textContent = "/ " + obj;
    $("s-suivi").classList.toggle("est-atteint", semaine >= obj);
    $("s-obj-txt").textContent = semaine >= obj ? "Objectif de la semaine atteint !" : "Encore " + pluriel(obj - semaine, "candidature") + " pour l'objectif de la semaine";

    // entonnoir
    var etapes = [["Repérées", offres.length], ["Retenues", compte.interesse + compte.postule], ["Postulé", compte.postule], ["Entretiens", entretiens], ["Pris·e", oui]];
    var max = Math.max(1, offres.length);
    var ent = $("s-entonnoir"); ent.textContent = "";
    etapes.forEach(function (e) {
      var ligne = el("div", "s-ent");
      ligne.appendChild(el("span", "s-ent-nom", e[0]));
      var barre = el("span", "s-ent-barre"); var plein = el("i");
      plein.style.width = (e[1] ? Math.max(2, e[1] / max * 100) : 0) + "%";
      barre.appendChild(plein); ligne.appendChild(barre);
      ligne.appendChild(el("b", "s-ent-n", e[1]));
      ent.appendChild(ligne);
    });

    // 8 dernières semaines
    var hist = $("s-histo"); hist.textContent = "";
    var sem = [];
    for (var k = 7; k >= 0; k--) sem.push(cetteSemaine - k * 7 * JOUR);
    var n = sem.map(function (deb) { return post.filter(function (i) { var t = Date.parse(i.d); return t >= deb && t < deb + 7 * JOUR; }).length; });
    var hmax = Math.max(obj, Math.max.apply(null, n));
    sem.forEach(function (deb, k) {
      var col = el("div", "s-col" + (n[k] >= obj ? " est-ok" : ""));
      var b = el("i"); b.style.height = Math.max(n[k] ? 6 : 2, n[k] / hmax * 100) + "%";
      col.title = "Semaine du " + jour(deb) + " : " + pluriel(n[k], "candidature");
      col.appendChild(el("span", "s-col-n", n[k] || ""));
      col.appendChild(b);
      col.appendChild(el("span", "s-col-j", new Date(deb).toLocaleDateString("fr-FR", { day: "numeric", month: "numeric" })));
      hist.appendChild(col);
    });
    var ligneObj = el("span", "s-histo-obj"); ligneObj.style.bottom = "calc(" + (obj / hmax * 100) + "% * .78 + 18px)";
    hist.appendChild(ligneObj);
    // série de semaines qui atteignent l'objectif (la semaine en cours compte si elle est déjà atteinte)
    var serie = 0;
    for (var s2 = n.length - 1; s2 >= 0; s2--) { if (n[s2] >= obj) serie++; else if (s2 !== n.length - 1) break; }
    $("s-serie").textContent = serie > 1 ? "🔥 " + serie + " semaines d'affilée à l'objectif" : "";
  }

  // ---------- affichage ----------
  var anciensComptes = {};
  function trier(liste) {
    if (vue === "trier") {
      var t = prefs.tri;
      liste.sort(function (a, b) {
        if (t === "recentes") return String(b.premiere || "").localeCompare(String(a.premiere || "")) || (b.score || 0) - (a.score || 0);
        if (t === "entreprise") return norm(a.entreprise).localeCompare(norm(b.entreprise));
        if (t === "compat") return compatFine(b) - compatFine(a) || (b.score || 0) - (a.score || 0) || String(b.premiere || "").localeCompare(String(a.premiere || ""));
        return (nouvelles[b.url] ? 1 : 0) - (nouvelles[a.url] ? 1 : 0) || (b.proche ? 1 : 0) - (a.proche ? 1 : 0) || (b.score || 0) - (a.score || 0);
      });
    } else {
      liste.sort(function (a, b) { return String(info(b).d).localeCompare(String(info(a).d)); });
    }
    return liste;
  }
  function afficher() {
    var compte = { trier: 0, interesse: 0, postule: 0, ecarte: 0 };
    offres.forEach(function (o) { compte[statut(o)]++; });
    Object.keys(compte).forEach(function (k) {
      var c = $("n-" + k); c.textContent = compte[k];
      if (anciensComptes[k] != null && anciensComptes[k] !== compte[k] && !calme) { c.classList.remove("bump"); void c.offsetWidth; c.classList.add("bump"); }
      anciensComptes[k] = compte[k];
    });
    bulle(compte);
    suivi(compte);

    var liste = trier(offres.filter(function (o) { return statut(o) === vue && passeFiltres(o); }));
    var cachees = 0;
    if (vue === "trier" && !voirTout && !filtre.q) {
      var visibles = SITE.compat
        ? liste.filter(function (o) { return compatibilite(o) >= SITE.compat.seuil; })
        : liste.filter(function (o) { return o.proche || nouvelles[o.url]; });
      cachees = liste.length - visibles.length;
      liste = visibles;
      if (SITE.compat) {
        $("s-plus-txt").textContent = "Ces offres collent moins à ton profil (CDI, poste confirmé, début trop tôt, lieu…). Touche la note d'une offre pour voir pourquoi.";
      }
    }

    $("s-aide").textContent = AIDES[vue];
    $("s-tri-zone").hidden = vue !== "trier";
    var ol = $("s-liste"); ol.textContent = "";
    if (!liste.length) {
      var vide = el("li", "s-vide");
      var mini = el("img", "s-mini"); mini.src = "bot.svg"; mini.alt = ""; vide.appendChild(mini);
      var filtres = filtre.ville || filtre.type || filtre.contrat || filtre.rse || filtre.q;
      vide.appendChild(el("strong", null, filtres ? "Aucune offre avec ces filtres" : VIDES[vue][0]));
      vide.appendChild(document.createTextNode(filtres ? "Enlève un filtre pour en voir plus." : VIDES[vue][1]));
      if (filtres) {
        var raz = el("button", "a-btn s-raz", "Enlever les filtres"); raz.type = "button";
        raz.addEventListener("click", razFiltres);
        vide.appendChild(raz);
      }
      ol.appendChild(vide);
    }
    liste.forEach(function (o, k) { ol.appendChild(carte(o, k)); });
    curseur = Math.min(curseur, liste.length - 1);
    marquerCurseur(false);

    $("s-plus").hidden = !cachees;
    $("s-plus-btn").textContent = "Voir " + cachees + " autre" + (cachees > 1 ? "s" : "") + " offre" + (cachees > 1 ? "s" : "");
  }

  // ---------- la bulle du robot ----------
  // Un message principal, le plus utile du moment ; toucher le robot fait défiler des astuces.
  var ASTUCES = [
    "Astuce : touche « ? » sur ordinateur pour voir les raccourcis clavier (j / k pour naviguer, g pour garder, x pour écarter).",
    "Astuce : sur téléphone, glisse une offre vers la droite pour la garder, vers la gauche pour l'écarter.",
    "Astuce : une offre retirée par le bot reste dans tes listes, avec l'étiquette « Plus en ligne ».",
    "Astuce : en bas de page, « Sauvegarder » crée un fichier de tes choix, à réimporter sur un autre appareil.",
    "Astuce : dans « Postulé », le bouton « Rappel agenda » ajoute la relance à J+10 dans ton calendrier.",
    "Astuce : la recherche fouille aussi dans tes notes.",
    "Astuce : la note /10 combine le contrat (3), le poste (3), tes outils (2), le lieu (1) et le niveau demandé (1), plus le début et le domaine."
  ];
  var astuce = -1, messagePrincipal = "";
  function meilleurePiste() {
    if (!SITE.compat) return null;
    var l = offres.filter(function (o) { return statut(o) === "trier"; }).sort(function (a, b) { return compatFine(b) - compatFine(a); });
    var o = l[0];
    return o ? "Ta meilleure piste du moment : « " + o.titre + " » chez " + o.entreprise + ", " + fmtNote(compatibilite(o)) + "/10." : null;
  }
  function bulle(compte) {
    var relances = offres.filter(aRelancer).length;
    var nouvATrier = offres.filter(function (o) { return nouvelles[o.url] && statut(o) === "trier"; }).length;
    var txt;
    if (!offres.length)
      txt = T.aucune;
    else if (premiereVisite && !compte.interesse && !compte.postule && !compte.ecarte)
      txt = SITE.compat ? T.bonjourCompat(offres.length, offres.filter(function (o) { return signauxOffre(o).contrat === SITE.compat.contratCible; }).length)
        : T.bonjour(pluriel(offres.length, T.des.replace(/s$/, "")));
    else if (nouvATrier)
      txt = nouvATrier + " " + (nouvATrier > 1 ? T.nouvP : T.nouv) + " depuis ta visite du " + jour(visitePrecedente) + " ! " + (nouvATrier > 1 ? (T.f ? "Elles sont" : "Ils sont") : (T.f ? "Elle est" : "Il est")) + " en haut de « À trier ».";
    else if (relances)
      txt = pluriel(relances, "candidature") + " envoyée" + (relances > 1 ? "s" : "") + " il y a plus de 10 jours. Un petit mail de relance ?";
    else if (compte.interesse)
      txt = pluriel(compte.interesse, "offre") + " " + accord(compte.interesse, "gardé", true) + " t'attend" + (compte.interesse > 1 ? "ent" : "") + " : " + T.gardees;
    else if (compte.postule)
      txt = "Déjà " + pluriel(compte.postule, "candidature") + ", bravo ! Je te préviens dès qu'" + (T.f ? "une " : "un ") + T.nouv + " arrive.";
    else if (compte.trier)
      txt = "Encore " + pluriel(compte.trier, "offre") + " à trier. Garde celles qui te plaisent, écarte les autres.";
    else
      txt = "Tout est trié ! Je te préviens dès qu'" + (T.f ? "une " : "un ") + T.nouv + " arrive.";
    if (txt !== messagePrincipal) { messagePrincipal = txt; astuce = -1; parler(txt); }
  }
  function parler(txt) {
    var b = $("s-bulle");
    if (b.textContent !== txt) { b.textContent = txt; b.style.animation = "none"; void b.offsetWidth; b.style.animation = ""; }
  }
  var robot = document.querySelector(".s-mii-cadre");
  if (robot) {
    robot.setAttribute("role", "button"); robot.tabIndex = 0;
    robot.setAttribute("aria-label", "Une astuce du robot");
    var parle = function () {
      var liste = meilleurePiste() ? [meilleurePiste()].concat(ASTUCES) : ASTUCES;
      astuce = (astuce + 1) % (liste.length + 1);
      parler(astuce === liste.length ? messagePrincipal : liste[astuce]);
      if (!calme) { robot.classList.remove("saute"); void robot.offsetWidth; robot.classList.add("saute"); }
    };
    robot.addEventListener("click", parle);
    robot.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); parle(); } });
  }

  if (DATA.date) $("s-maj").textContent = "Liste mise à jour le " + jour(DATA.date + "T12:00:00Z");

  // ---------- onglets, filtres, tri ----------
  function choisirVue(v) {
    vue = v; curseur = -1;
    document.querySelectorAll(".s-onglet").forEach(function (x) { x.setAttribute("aria-pressed", x.dataset.vue === v); });
    afficher();
  }
  document.querySelectorAll(".s-onglet").forEach(function (b) {
    b.addEventListener("click", function () { choisirVue(b.dataset.vue); });
  });
  function groupe(attr) {
    var zone = document.querySelectorAll(".s-filtre[data-" + attr + "]");
    if (!zone.length) return;
    zone[0].parentNode.addEventListener("click", function (e) {
      var b = e.target.closest(".s-filtre[data-" + attr + "]"); if (!b) return;
      filtre[attr] = b.dataset[attr];
      document.querySelectorAll(".s-filtre[data-" + attr + "]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      afficher();
    });
  }
  function razFiltres() {
    filtre = { ville: "", type: "", contrat: "", rse: false, q: "" };
    $("s-cherche").value = "";
    document.querySelectorAll(".s-filtre").forEach(function (x) {
      var attr = ["ville", "type", "contrat"].filter(function (a) { return x.dataset[a] != null; })[0];
      x.setAttribute("aria-pressed", attr ? x.dataset[attr] === "" : "false");
    });
    afficher();
  }
  // pastilles de ville construites d'après les offres, avec leur nombre
  var comptes = {}, comptesContrat = {};
  offres.forEach(function (o) { comptes[o.ville] = (comptes[o.ville] || 0) + 1; comptesContrat[o.contrat] = (comptesContrat[o.contrat] || 0) + 1; });
  var zoneVilles = $("f-villes");
  if (SITE.villesDynamiques && zoneVilles) {
    Object.keys(comptes).sort(function (a, b) { return comptes[b] - comptes[a]; }).forEach(function (k) {
      var b = el("button", "a-chip s-filtre", NOMS_VILLES[k] + " (" + comptes[k] + ")");
      b.type = "button"; b.dataset.ville = k; b.setAttribute("aria-pressed", "false"); zoneVilles.appendChild(b);
    });
  } else {
    document.querySelectorAll(".s-filtre[data-ville]").forEach(function (b) {
      var k = b.dataset.ville; if (k) b.textContent += " (" + (comptes[k] || 0) + ")";
    });
  }
  document.querySelectorAll(".s-filtre[data-contrat]").forEach(function (b) {
    var k = b.dataset.contrat; b.textContent += " (" + (k ? (comptesContrat[k] || 0) : offres.length) + ")";
  });
  groupe("ville"); groupe("type"); groupe("contrat");
  if ($("f-rse")) $("f-rse").addEventListener("click", function () { filtre.rse = !filtre.rse; this.setAttribute("aria-pressed", filtre.rse); afficher(); });
  var attente;
  $("s-cherche").addEventListener("input", function (e) { clearTimeout(attente); attente = setTimeout(function () { filtre.q = e.target.value; afficher(); }, 120); });
  $("s-plus-btn").addEventListener("click", function () { voirTout = true; afficher(); });
  $("s-tri").value = prefs.tri;
  $("s-tri").addEventListener("change", function () { prefs.tri = this.value; sauver(); afficher(); });

  // objectif de la semaine
  function objectif(d) { prefs.objectif = Math.max(1, Math.min(30, prefs.objectif + d)); sauver(); afficher(); }
  $("s-obj-moins").addEventListener("click", function () { objectif(-1); });
  $("s-obj-plus").addEventListener("click", function () { objectif(1); });
  var details = $("s-suivi-details");
  if (prefs.suiviOuvert) details.open = true;
  details.addEventListener("toggle", function () { prefs.suiviOuvert = details.open; sauver(); });

  (DATA.liens || []).forEach(function (l) {
    var a = el("a", null, l[0]); a.href = l[2]; a.target = "_blank"; a.rel = "noopener";
    a.appendChild(el("small", null, l[1]));
    $("s-liens").appendChild(a);
  });

  // ---------- clavier ----------
  function cartes() { return Array.prototype.slice.call(document.querySelectorAll("#s-liste .s-offre")); }
  function marquerCurseur(focus) {
    cartes().forEach(function (c, k) { c.classList.toggle("est-choisie", k === curseur); });
    var c = cartes()[curseur];
    if (c && focus) { c.focus({ preventScroll: true }); c.scrollIntoView({ block: "center", behavior: calme ? "auto" : "smooth" }); }
  }
  function offreCurseur() { var c = cartes()[curseur]; return c ? parUrl[c.dataset.url] : null; }
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) {
      if (e.key === "Escape") t.blur();
      return;
    }
    var k = e.key, n = cartes().length, o, c;
    if (k === "Escape") { $("s-aide-clavier").hidden = true; return; }
    if (k === "?") { $("s-aide-clavier").hidden = !$("s-aide-clavier").hidden; return; }
    if (k === "/") { e.preventDefault(); $("s-cherche").focus(); return; }
    if (k >= "1" && k <= "4") { choisirVue(["trier", "interesse", "postule", "ecarte"][k - 1]); return; }
    if (k === "j" || k === "ArrowDown" && curseur >= 0) { if (n) { e.preventDefault(); curseur = Math.min(n - 1, curseur + 1); marquerCurseur(true); } return; }
    if (k === "k" || k === "ArrowUp" && curseur >= 0) { if (n) { e.preventDefault(); curseur = Math.max(0, curseur - 1); marquerCurseur(true); } return; }
    o = offreCurseur(); c = cartes()[curseur];
    if (!o) return;
    var s = statut(o);
    if (k === "o" || k === "Enter") { memo.vues[o.url] = 1; sauver(); window.open(o.url, "_blank", "noopener"); afficher(); }
    else if (k === "g" && s === "trier") changer(o, "interesse", "Rangée dans « Gardées »", c, "droite");
    else if (k === "x" && (s === "trier" || s === "interesse")) changer(o, "ecarte", "Offre écartée", c, "gauche");
    else if (k === "p" && s === "interesse") { confettis(c); changer(o, "postule", "Bravo ! Rangée dans « Postulé »", c, "droite"); }
    else if (k === "u" && s !== "trier") changer(o, s === "postule" ? "interesse" : "trier", "Remise en arrière", c, "gauche");
  });
  $("s-aide-clavier").addEventListener("click", function (e) { if (e.target === this || e.target.closest("button")) this.hidden = true; });
  if ($("s-clavier-btn")) $("s-clavier-btn").addEventListener("click", function () { $("s-aide-clavier").hidden = false; });

  // ---------- sauvegarde / import / CSV ----------
  function telecharger(nom, contenu, type) {
    var a = el("a"); a.download = nom;
    a.href = URL.createObjectURL(new Blob([contenu], { type: type + ";charset=utf-8" }));
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  var aujourdhui = new Date().toISOString().slice(0, 10);
  $("s-export").addEventListener("click", function () {
    telecharger("mes-" + T.des + "-" + aujourdhui + ".json", JSON.stringify({ site: SITE.cle, date: aujourdhui, memo: memo }, null, 1), "application/json");
    toast("Sauvegarde téléchargée. Importe-la sur un autre appareil pour retrouver tes choix.");
  });
  $("s-import").addEventListener("change", function () {
    var f = this.files[0]; if (!f) return;
    var lecteur = new FileReader();
    lecteur.onload = function () {
      try {
        var d = JSON.parse(lecteur.result);
        if (!d.memo || d.site !== SITE.cle) throw new Error("fichier");
        ["statuts", "verif", "notes", "fiches", "vues"].forEach(function (k) { memo[k] = Object.assign({}, memo[k], d.memo[k] || {}); });
        sauver();
        toast("Choix importés : " + pluriel(Object.keys(d.memo.statuts || {}).length, "offre") + ". Rechargement…");
        setTimeout(function () { location.reload(); }, 900);
      } catch (e) { toast("Ce fichier n'est pas une sauvegarde de cette page."); }
    };
    lecteur.readAsText(f);
    this.value = "";
  });
  $("s-csv").addEventListener("click", function () {
    var lignes = [["Statut", "Offre", "Entreprise", "Lieu", "Postulé le", "Relancé le", "Entretien le", "Réponse", "Note", "Lien"]];
    var noms = { interesse: "Gardée", postule: "Postulé", ecarte: "Écartée" };
    function d(x) { return x ? new Date(x).toLocaleDateString("fr-FR") : ""; }
    offres.filter(function (o) { var s = statut(o); return s === "interesse" || s === "postule"; }).forEach(function (o) {
      var i = info(o);
      lignes.push([noms[i.s], o.titre, o.entreprise, o.lieu, i.s === "postule" ? d(i.d) : "", d(i.relance), d(i.entretien), i.reponse === "oui" ? "Oui" : i.reponse === "non" ? "Non" : "", memo.notes[o.url] || "", o.url]);
    });
    var csv = lignes.map(function (l) { return l.map(function (c) { return '"' + String(c == null ? "" : c).replace(/"/g, '""') + '"'; }).join(";"); }).join("\r\n");
    telecharger("mes-candidatures-" + aujourdhui + ".csv", "﻿" + csv, "text/csv");
  });

  // ---------- thème clair / sombre ----------
  var bTheme = $("s-theme");
  function majTheme() {
    var sombre = document.documentElement.dataset.theme === "dark";
    bTheme.textContent = sombre ? "☀" : "☾";
    bTheme.setAttribute("aria-label", sombre ? "Passer en thème clair" : "Passer en thème sombre");
    var mc = document.querySelector('meta[name="theme-color"]');
    if (mc) mc.content = getComputedStyle(document.documentElement).getPropertyValue("--a-bg").trim() || mc.content;
  }
  if (bTheme) {
    majTheme();
    bTheme.addEventListener("click", function () {
      var t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem("theme:" + SITE.cle, t); } catch (e) { /* tant pis */ }
      majTheme();
    });
  }

  // avancée du bootcamp : chargée en arrière-plan, la page s'affiche sans l'attendre
  if (SITE.bootcamp) {
    fetch(SITE.bootcamp.url, { cache: "no-cache" }).then(function (r) { if (!r.ok) throw r.status; return r.json(); }).then(function (b) {
      BOOT = window.BOOTCAMP = b;
      offres.forEach(function (o) { delete o._c; });   // la note dépend de l'avancée du bootcamp
      var enCours = b.competences.filter(function (c) { return c.etat === "en cours"; }).map(function (c) { return c.nom + " (" + c.pct + " %)"; });
      ASTUCES.unshift("Ton bootcamp : " + b.pct + " % des notions acquises" + (enCours.length ? ", en cours : " + enCours.join(", ") : "")
        + (b.en_cours && b.en_cours.notions.length ? ". Tu travailles " + b.en_cours.notions.join(", ") + "." : "."));
      ASTUCES.push("Astuce : chaque offre affiche les outils demandés, en vert ceux que tu maîtrises, en couleur ceux du bootcamp en cours. Trie par « Compétences » pour voir les plus accessibles.");
      afficher();
    }).catch(function () { /* pas de bootcamp.json (page ouverte en local) : on s'en passe */ });
  } else {
    var opt = document.querySelector('#s-tri option[value="competences"]');   // ancien libellé, plus utilisé
    if (opt) opt.remove();
  }

  afficher();
})();
