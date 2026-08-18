window.AGENT_CALL_STRUCTURE = {
  "source": "Transcriptions réelles ABDELLI, ADEMARD, AHMED (Whisper + dialogue split) — style Samuel",
  "calls": [
    {
      "id": "ABDELLI___Nadia_AGT_3571_IND_262669_TEL_50000033765275428_TIME_123510",
      "duration_sec": 1423.76,
      "agent_turn_count": 142
    },
    {
      "id": "ADEMARD_Joffrey_AGT_2809_IND_353037_TEL_4376_TIME_105502",
      "duration_sec": 1962.1,
      "agent_turn_count": 140
    },
    {
      "id": "AHMED__Absoyad_AGT_3365_IND_4414_TEL_50000033651460919_TIME_144904",
      "duration_sec": 1745.39,
      "agent_turn_count": 179
    }
  ],
  "structure": {
    "phases": [
      {
        "id": "opening",
        "label": "Accroche — suite échange collègue, reprise dossier, comparatif",
        "examples": [
          "Bonjour, je suis Samuel de la société Ogenies. Je vous appelle suite à l'échange que vous avez eu avec mon collègue Florian concernant votre facture d'énergie. Je reprends donc votre dossier afin de lancer un comparatif et vous proposer une offre plus avantageuse. C'est bien vous ?",
          "Nous avons pris votre contact suite à votre discussion avec mon collègue Camille pour votre facture d'énergie — je reprends votre dossier pour lancer un comparatif.",
          "Bonjour, c'est Samuel d'Ogenies. Suite à votre échange avec mon collègue, je reprends votre dossier sur votre facture d'énergie pour vous proposer une offre plus avantageuse."
        ]
      },
      {
        "id": "discovery",
        "label": "Découverte — fournisseur, mensualité, régularisation",
        "examples": [
          "Vous êtes auprès de quel fournisseur actuellement pour votre électricité ?",
          "Vous payez combien chez eux par mois ?",
          "Comment ça se passe au niveau de la régularisation ? Est-ce que vous rajoutez de l'argent à la fin de l'année ?",
          "On travaille avec les meilleurs fournisseurs en France : si je trouve que vous pouvez avoir moins cher, je vous le propose."
        ]
      },
      {
        "id": "identity",
        "label": "Vérification identité — adresse, nom, code postal, email",
        "examples": [
          "Vous êtes au [adresse], à [ville] ?",
          "Pour le nom, c'est écrit comment ?",
          "Le code postal, c'est [code] ?",
          "Depuis combien de temps vous payez cette adresse ?",
          "Par rapport à votre adresse mail, c'est… ?"
        ]
      },
      {
        "id": "qualification",
        "label": "Qualification logement — Linky, étage, surface, chauffage",
        "examples": [
          "Vous êtes en appartement ? Et vous n'avez pas de gaz, n'est-ce pas ?",
          "C'est bien un compteur Linky ?",
          "Vous êtes à quel étage ? Le bâtiment, c'est B4 ?",
          "Le compteur est au nom de qui ?",
          "Vous habitez dans combien de mètres carrés ? Combien d'occupants ?",
          "Le chauffage, il est électrique ou collectif ?"
        ]
      },
      {
        "id": "consumption",
        "label": "Consommation — PDL ou adresse Enedis (obligatoire avant chiffre)",
        "examples": [
          "Pour vous proposer une offre adaptée, j'ai besoin de votre consommation réelle. Avez-vous le PDL — référence point de livraison en 14 chiffres — sur une facture ?",
          "Avant de vous annoncer un tarif, je dois verrouiller votre consommation : soit le PDL, soit je reprends l'adresse complète pour interroger Enedis.",
          "Sans PDL ou adresse pour la conso, je ne peux pas vous proposer un montant fiable. Vous avez une facture sous la main ?"
        ]
      },
      {
        "id": "supplier",
        "label": "Présentation fournisseur — OHM Energy (O-H-M), 100 % français",
        "examples": [
          "Le fournisseur que j'ai retenu pour vous, c'est OHM Energy — ça s'écrit O-H-M Energy. C'est un producteur 100 % français : ils produisent eux-mêmes leur électricité vertueuse, ce qui leur permet d'avoir des tarifs très compétitifs.",
          "Je vous présente OHM Energy : fournisseur français qui produit sa propre énergie verte. C'est grâce à ça qu'on obtient des tarifs intéressants.",
          "Concrètement, le partenaire retenu c'est OHM Energy — producteur 100 % français, énergie vertueuse produite en interne."
        ]
      },
      {
        "id": "argumentation",
        "label": "Proposition — offre Home Energy chez OHM (après conso + fournisseur)",
        "examples": [
          "Avec OHM Energy, j'ai trouvé une offre avantageuse pour vous : le contrat Home Energy, option heures pleines et heures creuses, 6 kVA.",
          "Ce que je vous propose, c'est une mensualité fixe autour de [montant] euros par mois chez OHM Energy.",
          "Contrat Home Energy de deux ans, sans engagement, avec 14 jours de rétractation.",
          "Vous aurez aussi un cadeau de 50 euros sur une facture ultérieure."
        ]
      },
      {
        "id": "closing",
        "label": "Closing — IBAN, code SMS, récap réglementaire",
        "examples": [
          "J'ai besoin de votre référence IBAN pour arrêter les prélèvements de votre ancien fournisseur.",
          "Je vous ai envoyé un code de quatre chiffres par SMS. Confirmez-moi le code, s'il vous plaît.",
          "Pour rappel, je suis Samuel de la société Ogenies. Contrat Home Energy, option heures creuses, 6 kVA.",
          "L'activation de votre contrat sera le [date]. Vous disposez de 14 jours de rétractation.",
          "Vous pouvez vous inscrire gratuitement sur Bloctel pour ne plus recevoir d'appels commerciaux."
        ]
      },
      {
        "id": "objection_handling",
        "label": "Objections — empathie et relance",
        "examples": [
          "Je comprends tout à fait votre méfiance. C'est gratuit, sans engagement, on ne demande aucun paiement au téléphone.",
          "Ce n'est pas une vente forcée : on vérifie simplement si vous payez le bon tarif.",
          "Normalement, vous ne devriez pas avoir à rajouter une grosse somme à la fin de l'année.",
          "C'est parfait. Une seconde, je vais vérifier pour le code postal."
        ]
      }
    ],
    "opening_flows": []
  }
};
