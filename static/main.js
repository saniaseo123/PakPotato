document.addEventListener("DOMContentLoaded", function () {

    const STORAGE_KEY = "pakpotato-language";

    function applyLanguage(lang) {

        const urdu = lang === "ur";

        document.documentElement.lang = urdu ? "ur" : "en";
        document.documentElement.dir = urdu ? "rtl" : "ltr";
        document.body.classList.toggle("urdu", urdu);

        document.querySelectorAll("[data-en][data-ur]").forEach(function (element) {

            const english = element.getAttribute("data-en");
            const urduText = element.getAttribute("data-ur");

            if (element.tagName === "INPUT" ||
                element.tagName === "TEXTAREA") {

                element.placeholder = urdu ? urduText : english;

            } else {

                element.innerHTML = urdu ? urduText : english;
            }
        });

        document.querySelectorAll("[data-lang]").forEach(function (button) {

            button.classList.toggle(
                "active",
                button.getAttribute("data-lang") === lang
            );
        });

        localStorage.setItem(STORAGE_KEY, lang);
    }

    document.addEventListener("click", function (event) {

        const button = event.target.closest("[data-lang]");

        if (!button) return;

        event.preventDefault();

        applyLanguage(button.getAttribute("data-lang"));
    });

    const savedLanguage =
        localStorage.getItem(STORAGE_KEY) || "en";

    applyLanguage(savedLanguage);
});

