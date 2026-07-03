# F1ATB Solar Router — intégration Home Assistant

Intégration **Home Assistant** pour le [routeur solaire F1ATB](https://github.com/F1ATB/Solar-Router-F1ATB)
(RMS ESP32), qui fonctionne avec le **firmware officiel, sans aucune modification**.

Elle parle au routeur via son **API HTTP locale** (`local_polling`) pour **piloter** le routage
depuis Home Assistant. La lecture des mesures (puissances, énergies…) reste disponible via la
publication MQTT native du firmware ; cette intégration se concentre sur le **contrôle**.

## Fonctionnalités

L'intégration est **dynamique** : les entités n'apparaissent **que pour les actions actives**
(une action dont la forme d'onde est « Inactif » n'a aucune entité). Dès qu'une action devient
active/inactive (depuis HA ou l'interface web du routeur), les entités apparaissent/disparaissent.

Par action active :

| Entité | Type | Réglage | Endpoint |
|---|---|---|---|
| **Forme d'onde** | `select` | Inactif / Découpe (ou On-Off) / Demi-sinus / Multi-sinus / Train de sinus / PWM | `/ParaNew` (persistant) |
| **Ouverture max** | `number` (0-100 %) | ouverture max si forcée (`ForceOuvre`) | `/ParaNew` (persistant) |
| **Forçage** | `select` | Auto / Marche forcée / Arrêt forcé | `/ForceAction` |
| **Ouverture** | `sensor` (%) | ouverture instantanée du routage | lecture |

Capteurs globaux : Soutirée réseau, Injectée réseau, Puissance routée, Énergie routée aujourd'hui.

## Installation (HACS — dépôt personnalisé)

1. HACS → menu ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/WillSpecIm/Integration-f1atb` — Catégorie : **Integration**
3. Installer, redémarrer Home Assistant
4. **Paramètres → Appareils & services → Ajouter une intégration → F1ATB Solar Router**
5. Saisir l'**adresse IP** du routeur (ex. `192.168.1.101`)

## Options

- **Intervalle d'interrogation** (défaut 5 s)
- **Durée d'un forçage** en minutes (défaut 720 = 12 h) : durée appliquée quand on choisit
  « Marche forcée » ou « Arrêt forcé » (le firmware décompte puis repasse en Auto).

## Carte Lovelace interactive

Une carte stylée est fournie : elle **auto-détecte** les entités de l'intégration et affiche,
par action active, la forme d'onde (boutons), l'ouverture max (slider) et le forçage
(Auto / Marche forcée / Arrêt forcé), plus les puissances de routage.

**La carte est chargée automatiquement par l'intégration** — rien à installer. Une fois
l'intégration ajoutée :
1. Sur un tableau de bord → **Ajouter une carte** → chercher **« F1ATB Solar Router »**
   (elle apparaît avec un aperçu dans le sélecteur graphique)
2. C'est tout : la carte trouve le routeur toute seule (aucune option à configurer)

> Si elle n'apparaît pas tout de suite : videz le cache du navigateur (Ctrl+F5) après le
> redémarrage de Home Assistant. En dernier recours, `f1atb-card.js` peut être ajouté
> manuellement en ressource (`/f1atb/f1atb-card.js`).

## Comment ça marche

- Lecture : `/ajax_data`, `/ajax_etatActions`, `/ajax_dataESP32`
- Config : `/ParaFixe` (mode `Actif`, `ForceOuvre`)
- Écriture d'un réglage persistant : lecture de la config complète → modification du seul champ
  concerné → renvoi via `/ParaNew` (exactement comme le bouton « Sauvegarder » de l'UI web).
- Forçage : `/ForceAction?NumAction=…&Force=…`

Aucune clé d'accès n'est requise (les endpoints ajax et `/ForceAction` ne la vérifient pas).

## Licence

MIT.
