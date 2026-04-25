CREATE FUNCTION calcular_totales_remision(p_remision_id INT)
RETURNS JSON
BEGIN
  DECLARE total_incubable INT DEFAULT 0;
  DECLARE total_sucio INT DEFAULT 0;
  DECLARE total_roto INT DEFAULT 0;
  DECLARE total_extra INT DEFAULT 0;
  DECLARE total_huevos INT DEFAULT 0;
  DECLARE cajas INT DEFAULT 0;
  DECLARE cubetas INT DEFAULT 0;
  DECLARE cubetas_sobrantes INT DEFAULT 0;

  SELECT 
    SUM(huevo_incubable),
    SUM(huevo_sucio),
    SUM(huevo_roto),
    SUM(huevo_extra)
  INTO total_incubable, total_sucio, total_roto, total_extra
  FROM remision_detalles 
  WHERE remision_id = p_remision_id;

  SET total_huevos = total_incubable + total_sucio + total_roto + total_extra;
  SET cajas = total_incubable DIV 360;
  SET cubetas = total_incubable DIV 30;
  SET cubetas_sobrantes = (total_incubable % 360) DIV 30;

  RETURN JSON_OBJECT(
    'total_incubable', total_incubable,
    'total_sucio', total_sucio,
    'total_roto', total_roto,
    'total_extra', total_extra,
    'total_huevos', total_huevos,
    'cajas', cajas,
    'cubetas', cubetas,
    'cubetas_sobrantes', cubetas_sobrantes
  );
END$$

