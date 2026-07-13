(function () {
  const Streamlit = {
    RENDER_EVENT: "streamlit:render",
    events: new EventTarget(),
    args: {},
    setComponentValue: function (value) {
      window.parent.postMessage(
        { isStreamlitMessage: true, type: "streamlit:setComponentValue", value: value },
        "*"
      );
    },
    setFrameHeight: function (height) {
      window.parent.postMessage(
        { isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: height },
        "*"
      );
    },
    setComponentReady: function () {
      window.parent.postMessage(
        { isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1 },
        "*"
      );
    },
  };

  window.Streamlit = Streamlit;

  window.addEventListener("message", function (event) {
    const data = event.data || {};
    if (data.type !== "streamlit:render") return;
    Streamlit.args = data.args || {};
    Streamlit.events.dispatchEvent(new Event(Streamlit.RENDER_EVENT));
  });

  window.addEventListener("load", function () {
    Streamlit.setComponentReady();
  });
})();
