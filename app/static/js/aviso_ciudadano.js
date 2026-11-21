"use strict";

(() => {
    const modalElemento = document.getElementById("modal-aviso");
    if (!modalElemento) return;
    const modal = new bootstrap.Modal(modalElemento);
    const formulario = document.getElementById("form-aviso");
    const nombrePunto = document.getElementById("aviso-punto-nombre");
    const error = document.getElementById("aviso-error");
    const exito = document.getElementById("aviso-exito");
    const botonEnviar = document.getElementById("btn-enviar-aviso");
    let puntoId = null;

    document.addEventListener("click", (evento) => {
        const boton = evento.target.closest(".btn-avisar-problema");
        if (!boton) return;
        puntoId = boton.dataset.puntoId;
        nombrePunto.textContent = boton.dataset.puntoNombre || "Punto de reciclaje";
        formulario.reset();
        error.classList.add("d-none");
        exito.classList.add("d-none");
        botonEnviar.disabled = false;
        modal.show();
    });

    formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        error.classList.add("d-none");
        exito.classList.add("d-none");
        const tipo = formulario.querySelector('input[name="tipo"]:checked')?.value;
        const comentario = document.getElementById("aviso-comentario").value.trim();
        if (!tipo) {
            error.textContent = "Selecciona un problema para continuar.";
            error.classList.remove("d-none");
            return;
        }
        botonEnviar.disabled = true;
        try {
            const respuesta = await fetch(modalElemento.dataset.endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/json", "Accept": "application/json"},
                body: JSON.stringify({punto_id: Number(puntoId), tipo, comentario})
            });
            const datos = await respuesta.json();
            if (respuesta.ok && datos.ok) {
                exito.textContent = datos.mensaje || "Gracias. El operador verá tu aviso en su panel.";
                exito.classList.remove("d-none");
                formulario.querySelectorAll("input, textarea, button").forEach(
                    elemento => { elemento.disabled = true; });
                setTimeout(() => modal.hide(), 2000);
            } else {
                error.textContent = datos.error || "No pudimos enviar el aviso. Revisa tu conexión e inténtalo de nuevo.";
                error.classList.remove("d-none");
                botonEnviar.disabled = false;
            }
        } catch {
            error.textContent = "No pudimos enviar el aviso. Revisa tu conexión e inténtalo de nuevo.";
            error.classList.remove("d-none");
            botonEnviar.disabled = false;
        }
    });

    modalElemento.addEventListener("hidden.bs.modal", () => {
        formulario.querySelectorAll("input, textarea, button").forEach(
            elemento => { elemento.disabled = false; });
    });
})();
