// SenseiCoin-награда: подпись Telegram проверяет сервер, клиент лишь просит выплату.
(() => {
  const initData = () => window.Telegram?.WebApp?.initData || "";
  const post = async (action, body) => {
    const response = await fetch(`/miniapp/dojo/api/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ initData: initData(), ...body }),
    });
    let data = {};
    try {
      data = await response.json();
    } catch {}
    if (!response.ok) throw Error(data.error || "Сервер награды недоступен.");
    return data;
  };
  let run = Promise.resolve(null);
  let lastError = "";
  window.DojoEconomy = {
    get available() {
      return Boolean(initData());
    },
    begin() {
      lastError = "";
      if (!this.available) {
        run = Promise.resolve(null);
        return run;
      }
      run = post("start", {}).catch((error) => {
        lastError = error.message;
        return null;
      });
      return run;
    },
    async finish(wave, victory) {
      if (!this.available)
        return {
          offline: true,
          error: "SenseiCoin начисляются только внутри Telegram.",
        };
      const started = await run;
      if (!started?.run)
        return {
          error: lastError || "Забег не зарегистрирован. Перезапусти игру.",
        };
      try {
        return await post("claim", {
          run: started.run,
          wave,
          victory,
        });
      } catch (error) {
        return { error: error.message };
      }
    },
  };
})();
