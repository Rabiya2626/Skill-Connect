document.addEventListener("click", function (event) {
  var button = event.target.closest("[data-password-toggle]");
  if (!button) return;
  var input = document.getElementById(button.getAttribute("data-password-toggle"));
  if (!input) return;
  var reveal = input.type === "password";
  input.type = reveal ? "text" : "password";
  button.setAttribute("aria-pressed", String(reveal));
  button.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
  button.textContent = reveal ? "Hide" : "Show";
});
