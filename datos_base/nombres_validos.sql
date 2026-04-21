/*En este archivo en el campo NOMBRE_PDF estan los nombres de los archivos PDF que se pueden utilizar en el sistema.
te explico como funciona el proceso hay un sistema hospitalario que se encarga de generar los PDFs y los guarda en una carpeta específica con nombres
no estandarizados. Por ejemplo, el nombre del archivo puede ser "PI_20230101.pdf" o "CC_20230102.pdf".
pero un compañero ya esta determinando las reglas para generar los nombres de los archivos PDF.
que deben ser cambiados a comop estan en el campo NOMBRE_PDF esos si son validos.

*/

Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('PI.pdf', 'S', 1, 'Planilla Individual', TO_TIMESTAMP('24/03/2026 8:03:56,456690','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('CC.pdf', 'S', 2, 'Consulta de Cobertura', TO_TIMESTAMP('24/03/2026 8:03:56,518093','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('CV.pdf', 'S', 3, 'Codigo de Validacion para la RCP', TO_TIMESTAMP('24/03/2026 8:03:56,569420','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('AES.pdf', 'S', 4, 'Acta entrega de servicio', TO_TIMESTAMP('24/03/2026 8:03:56,815195','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('053.pdf', 'S', 5, 'Copia formulario 053/referencia-Derivacion', TO_TIMESTAMP('24/03/2026 8:03:56,907538','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('006.pdf', 'S', 6, 'Copia formulario 006/Epicrisis', TO_TIMESTAMP('24/03/2026 8:03:57,004723','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('007.pdf', 'S', 7, 'Copia formulario 007/Interconsulta', TO_TIMESTAMP('24/03/2026 8:03:57,211656','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('017.pdf', 'S', 8, 'Copia formulario Protocolo Quirurgico', TO_TIMESTAMP('24/03/2026 8:03:57,328118','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('018.pdf', 'S', 9, 'Copia formulario Protocolo Anestesico', TO_TIMESTAMP('24/03/2026 8:03:57,438559','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('018A.pdf', 'S', 10, 'Copia formulario Protocolo Transanestesico', TO_TIMESTAMP('24/03/2026 8:03:57,543632','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('113.pdf', 'S', 11, 'Copia de la Bitacora Diaria para Hospitalizacion en terapia intensiva', TO_TIMESTAMP('24/03/2026 8:03:57,639162','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('114.pdf', 'S', 12, 'Copia de la Bitacora Diaria para Hospitalizacion en terapia intensiva neonatal', TO_TIMESTAMP('24/03/2026 8:03:57,745956','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('115.pdf', 'S', 13, 'Copia de la Bitacora Diaria para Hospitalizacion en terapia intensiva pediatrica', TO_TIMESTAMP('24/03/2026 8:03:57,855514','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('ORS.pdf', 'S', 14, 'Otros relacionados al servicio', TO_TIMESTAMP('24/03/2026 8:03:57,969313','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('002.pdf', 'S', 15, 'Copia formulario 002/consulta externa', TO_TIMESTAMP('24/03/2026 8:03:58,064067','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('010A.pdf', 'S', 16, 'Copia formulario 010A/Laboratorio pedido', TO_TIMESTAMP('24/03/2026 8:03:58,178733','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('010B.pdf', 'S', 17, 'Copia formulario 010B/Laboratorio informe', TO_TIMESTAMP('24/03/2026 8:03:58,271182','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('012A.pdf', 'S', 18, 'Copia formulario 012/Imagen pedido', TO_TIMESTAMP('24/03/2026 8:03:58,562089','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('012B.pdf', 'S', 19, 'Copia formulario 012/Imagen informe', TO_TIMESTAMP('24/03/2026 8:03:58,655195','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('033.pdf', 'S', 20, 'Copia formulario 033/Odontologia', TO_TIMESTAMP('24/03/2026 8:03:58,851524','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('013A.pdf', 'S', 21, 'Copia del formulario 013/Histopatologia pedido', TO_TIMESTAMP('24/03/2026 8:03:59,059822','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('013B.pdf', 'S', 22, 'Copia del formulario 013/Histopatologia informe', TO_TIMESTAMP('24/03/2026 8:03:59,522261','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('PTR.pdf', 'S', 23, 'Copia de pedido de terapias de rehabilitacion', TO_TIMESTAMP('24/03/2026 8:03:59,604415','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('RTR.pdf', 'S', 24, 'Registro de terapias recibidas (rehabilitacion)', TO_TIMESTAMP('24/03/2026 8:03:59,839778','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('08.pdf', 'S', 25, 'Copia formulario 008/Emergencia', TO_TIMESTAMP('24/03/2026 8:03:59,934440','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('FSCS.pdf', 'S', 26, 'Original del Formulario de solicitud de componentes sanguineos', TO_TIMESTAMP('24/03/2026 8:04:00,006709','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('FSICS.pdf', 'S', 27, 'Original del Formulario de solicitud intrahospitalaria de componentes sanguineos', TO_TIMESTAMP('24/03/2026 8:04:00,190670','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('FRDCS.pdf', 'S', 28, 'Original del Formulario de Registro de despacho de componentes sanguineos', TO_TIMESTAMP('24/03/2026 8:04:00,280243','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('ANX2.pdf', 'S', 29, 'Copia Anexo 2/Atencion Prehospitalaria', TO_TIMESTAMP('24/03/2026 8:04:00,477578','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('HR.pdf', 'S', 30, 'Copia de la hoja de Ruta', TO_TIMESTAMP('24/03/2026 8:04:00,565705','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('RHD.pdf', 'S', 31, 'Reporte de hemodialisis diario por cada mes por paciente', TO_TIMESTAMP('24/03/2026 8:04:00,666984','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('IMT.pdf', 'S', 32, 'Informe medico trimestral', TO_TIMESTAMP('24/03/2026 8:04:00,811658','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('CEC.pdf', 'S', 33, 'Copias de los resultados de examenes complementarios', TO_TIMESTAMP('24/03/2026 8:04:00,888474','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('RAD.pdf', 'S', 34, 'Registro de asistencia', TO_TIMESTAMP('24/03/2026 8:04:00,988932','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('ITS.pdf', 'S', 35, 'Informe semestral de trabajo social', TO_TIMESTAMP('24/03/2026 8:04:01,241388','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('RVD.pdf', 'S', 36, 'Registro mensual de visita domiciliaria u hoja de ruta', TO_TIMESTAMP('24/03/2026 8:04:01,316145','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
Insert into PDF_NOMBRES_VALIDOS
   (NOMBRE_PDF, ACTIVO, ORDEN, NOTA, CREATED_AT_UTC)
 Values
   ('119.pdf', 'S', 38, 'Formulario Ambulancia', TO_TIMESTAMP('24/03/2026 8:10:52,106803','DD/MM/YYYY fmHH24fm:MI:SS,FF'));
COMMIT;
