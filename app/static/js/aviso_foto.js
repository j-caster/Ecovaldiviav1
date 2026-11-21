"use strict";

(() => {
    const modalElemento = document.getElementById("modal-foto-aviso");
    const imagen = document.getElementById("foto-aviso-grande");
    if (!modalElemento || !imagen) return;
    const modal = new bootstrap.Modal(modalElemento);

    document.addEventListener("click", (evento) => {
        const boton = evento.target.closest(".btn-ver-foto");
        if (!boton) return;
        imagen.src = boton.dataset.fotoUrl;
        modal.show();
    });

    modalElemento.addEventListener("hidden.bs.modal", () => {
        imagen.src = "";
    });
})();
