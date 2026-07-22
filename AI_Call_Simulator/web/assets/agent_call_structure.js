window.AGENT_CALL_STRUCTURE = {
  "source": "Transcriptions réelles ABDELLI, ADEMARD, AHMED (Whisper + dialogue split)",
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
        "label": "Accroche — présentation + objet de l'appel",
        "examples": [
          "C'est Samuel de Société Ogini, je vous appelle concernant vos factures d'électricité, c'est vous qui gérez ?",
          "Vous m'avez contacté... Oui monsieur, c'est Yann de la société Ogini et je vous appelle pour la vérification de votre consommation",
          "j'ai oublié de vous annoncer, c'est que vous allez avoir, madame, un cadeau de 50 euros qu'on va n'avoir sur les factures",
          "Pour rappel, je suis monsieur Eric de la société au génie.com. Je vous ai contacté aujourd'hui pour vous proposer un contrat",
          "pour vous proposer un contrat de fourniture d'électricité, de home énergie, d'accord ?",
          "Point de livraison, PDL, qui est... C'est une référence sur la facture d'électricité. Le point de relèvement de mesure, c'est ça, PRL ?"
        ]
      },
      {
        "id": "discovery",
        "label": "Découverte — fournisseur, facture, consommation",
        "examples": [
          "Donc, vous payez à la consommation, c'est très bien. Vous avez une idée par rapport au prix de kWh actuel auprès de Alpique ou pas ?",
          "Vous payez combien par mois, s'il vous plaît, madame ?",
          "Madame, est-ce que vous avez une idée combien vous payez pour le prix de kWh ?",
          "Le chauffage, il est électrique individuel ou bien il est à gaz ?",
          "Donc vous êtes prélevée toujours le 30. Du coup, pour ce mois-ci, vous n'avez pas encore eu le prélèvement ? Pas encore, mais j'ai eu la facture",
          "Bien sûr, madame, vous m'autorisez à accéder à vos données de consommation annuelles ?"
        ]
      },
      {
        "id": "comparatif",
        "label": "Comparatif — gratuit, sans engagement, indépendant",
        "examples": [
          "Votre contrat est sans engagement. Je vous rappelle que vous disposez d'un délai",
          "Et le contrat est conclu pour une durée déterminée, bien sûr, le contrat est de deux ans, et bien sûr, le contrat est sans engagement, et je vous rappelle que vous disposez",
          "Madame, est-ce que vous voulez qu'on lance un comparatif ? Cette opération ne prend pas plus de 5 minutes, d'accord ?",
          "Donc, en tant que abonnée au génie, vous avez profité d'un comparatif gratuit",
          "Et c'est aussi que vous avez un délai de rétractation de 14 jours",
          "Pour terminer, madame, je vous informe que vous pouvez vous inscrire gratuitement"
        ]
      },
      {
        "id": "argumentation",
        "label": "Argumentation — chiffres, économies, valeur",
        "examples": [
          "Alors, ce que je vous propose aujourd'hui, monsieur, un prix du kWh qui est moins cher, d'accord ?",
          "Donc comme je viens de vous dire, madame, l'offre la plus adaptée pour vous, ce sera l'offre de Home Energy",
          "Cela vous permet de prendre le temps de réfléchir à cette offre",
          "les coordonnées communiquées préalablement ? Vous êtes bien, monsieur Adhemar Joffrey ?",
          "comme d'habitude ? Oui, vous consommez comme d'habitude au moins cher ou plus cher ?",
          "Donc, l'offre que je vous ai proposé, madame, c'est l'offre HomeFix"
        ]
      },
      {
        "id": "closing",
        "label": "Closing — coordonnées, IBAN, confirmation",
        "examples": [
          "Madame, vous pouvez me confirmer avec moi votre adresse e-mail, s'il vous plaît ?",
          "J'ai besoin de votre référence IBAN, le RIB, pour arrêter les prélèvements de Alpique",
          "à la suite de notre appel. Vous m'avez indiqué choisir l'option Earthplane or Cause et vous me confirmez",
          "Vous me confirmez avoir bien compris, madame, que l'activation de votre contrat sera le 25",
          "Maintenant, madame, je vous ai envoyé un code de quatre chiffres par SMS. Donc, s'il vous plaît, confirmez-moi",
          "Madame, vous pouvez me donner votre adresse ? Alors c'est 45 rue Général Leclerc, 93 000 fondis, à Renisebois. Vous pouvez répéter pour l'écrire le 45 rue ?"
        ]
      },
      {
        "id": "objection_handling",
        "label": "Objections — empathie et relance",
        "examples": [
          "Une seconde, madame, s'il vous plaît. Madame, vous pouvez me donner votre date de naissance ?",
          "Une seconde, madame, s'il vous plaît. Madame, votre ville, c'est Rosny-Sauvois, c'est ça ?",
          "Et s'il vous plaît, madame, on est bien d'accord que vous n'êtes ni sous tutelle, ni sous curatelle ?",
          "Donc on va garder le réel. C'est parfait, madame. Donc là, dites-moi s'il vous plaît, vous êtes prélevée quand auprès de Alpique ?",
          "C'est parfait, madame. Vous avez que l'électricité. Il n'y a pas de gaz à la maison ?",
          "Une seconde, s'il vous plaît. Madame, je vous passe mon responsable"
        ]
      }
    ],
    "opening_flows": []
  }
};
