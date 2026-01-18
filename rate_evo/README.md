# Venezuela - Moneda dual (Evolsys)

Módulo para Odoo 19 que extiende la gestión de tasas de cambio y precios convertidos, integrando las tasas oficiales del **Banco Central de Venezuela (BCV)** y añadiendo auditoría y trazabilidad completa.

---

## ✨ Características principales

- **Proveedor BCV**: configuración automática del proveedor de tasas del Banco Central de Venezuela.
- **Precios convertidos**: muestra el PU Convertido en:
  - Facturas (`account.move`)
  - Pedidos de venta (`sale.order.line`)
  - Pedidos de compra (`purchase.order.line`)
- **Auditoría**: registro automático de cambios en `res.currency.rate` con trazabilidad de usuario, fecha y motivo.
- **Logs de importación**: historial de importaciones de tasas desde proveedores.
- **Tasa en cabecera**: visible en facturas y pedidos, calculada automáticamente.
- **Wizard de pagos**: tasa visible y editable solo para usuarios con permisos de manager.
- **Seguridad**: control de accesos mediante grupos:
  - `Rate Evo Usuario`: solo lectura.
  - `Rate Evo Manager`: control total.

---

## 📦 Dependencias

Este módulo depende de:
- `account`
- `sale`
- `purchase`

---

## 🚀 Instalación

1. Copiar el módulo en la carpeta `addons` de Odoo.
2. Actualizar la lista de módulos desde la interfaz de Odoo.
3. Instalar **Rate Evo**.
4. Al instalar, se activa automáticamente el proveedor BCV y se programa la actualización diaria de tasas.

---

## 🛠️ Uso

- **Facturas y pedidos**: verás la tasa de cambio en la cabecera y el PU Convertido en las líneas.
- **Wizard de pagos**: la tasa aparece y puede ser modificada por usuarios del grupo **Rate Evo Manager**.
- **Menú Rate Evo**:
  - Auditoría de Tasas: historial de cambios en `res.currency.rate`.
  - Logs de Tasas: historial de importaciones desde BCV.

---

## 🔒 Seguridad

- **Usuarios**: pueden consultar auditoría y logs, ver tasas en documentos y wizard.
- **Managers**: pueden modificar la tasa en el wizard de pagos y administrar auditoría/logs.

---

## 📑 Licencia

LGPL-3
