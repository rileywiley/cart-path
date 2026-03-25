-- CartPath — Custom OSRM Lua Profile for Golf Cart Routing
-- =========================================================
-- Routes only on roads with speed limits ≤35 MPH.
-- Penalizes unpaved surfaces and service roads.
-- Excludes driveways and parking aisles entirely.
-- Penalizes crossing >35 MPH roads at unsignalized intersections.
-- Prefers lighted (signalized) crossings of major roads.

api_version = 4

Set = require('lib/set')
Sequence = require('lib/sequence')

function setup()
  return {
    properties = {
      max_speed_for_map_matching = 60 / 3.6, -- km/h
      weight_name = 'duration',
      u_turn_penalty = 20,
      traffic_signal_penalty = 2,
      continue_straight_at_waypoint = true,
      use_turn_restrictions = true,
    },

    default_mode = mode.driving,
    default_speed = 37, -- 23 MPH in km/h (default cart speed)

    -- Speed constants (in km/h for OSRM)
    cart_speed_kmh = 37,          -- 23 MPH
    service_speed_kmh = 16,       -- 10 MPH
    max_legal_speed_mph = 35,
    penalty_unpaved = 0.5,        -- 50% speed reduction for unpaved

    -- Crossing penalties (seconds) — applied at intersections with >35 MPH roads
    unsignalized_crossing_penalty = 45,  -- Heavy penalty: discourage unlit crossings
    signalized_crossing_bonus = -5,      -- Small bonus: prefer lighted intersections

    -- Road types that carts can use
    cart_road_types = Set {
      'primary', 'primary_link',
      'secondary', 'secondary_link',
      'tertiary', 'tertiary_link',
      'residential', 'unclassified',
      'living_street', 'service',
    },

    -- Service subtypes to exclude
    excluded_service_types = Set {
      'driveway',
      'parking_aisle',
    },
  }
end

function process_node(profile, node, result, relations)
  -- Handle traffic signals
  local highway = node:get_value_by_key('highway')
  if highway == 'traffic_signals' then
    result.traffic_lights = true
  end

  -- Handle CartPath crossing penalties for major-road intersections
  local crossing_signal = node:get_value_by_key('cartpath:crossing_signal')
  local crossing_speed = node:get_value_by_key('cartpath:crossing_speed')

  if crossing_signal and crossing_speed then
    local speed = tonumber(crossing_speed) or 0
    if speed > profile.max_legal_speed_mph then
      if crossing_signal == 'no' then
        -- Unsignalized crossing of a >35 MPH road: heavy penalty
        result.barrier = true
        result.duration_penalty = profile.unsignalized_crossing_penalty
      elseif crossing_signal == 'yes' then
        -- Signalized crossing: small bonus (negative penalty = preference)
        result.duration_penalty = profile.signalized_crossing_bonus
      end
    end
  end
end

function process_way(profile, way, result, relations)
  local highway = way:get_value_by_key('highway')

  -- Only process road types relevant to golf carts
  if not highway or not profile.cart_road_types[highway] then
    return
  end

  -- Exclude specific service road subtypes
  if highway == 'service' then
    local service_type = way:get_value_by_key('service')
    if service_type and profile.excluded_service_types[service_type] then
      return
    end
  end

  -- Read CartPath custom tags
  local cart_legal = way:get_value_by_key('cartpath:cart_legal')
  local routing_speed_str = way:get_value_by_key('cartpath:routing_speed')
  local surface_type = way:get_value_by_key('cartpath:surface_type')
  local maxspeed_str = way:get_value_by_key('maxspeed')

  -- Parse maxspeed to determine legality
  local maxspeed_mph = nil
  if maxspeed_str then
    maxspeed_mph = tonumber(maxspeed_str)
  end

  -- Determine if this road is cart-legal
  local is_cart_legal = true
  if cart_legal == 'false' then
    is_cart_legal = false
  elseif maxspeed_mph and maxspeed_mph > profile.max_legal_speed_mph then
    is_cart_legal = false
  end

  -- Set base speed
  local speed = profile.cart_speed_kmh  -- 23 MPH default

  if not is_cart_legal then
    -- Non-compliant roads: assign very high weight (slow speed = high cost)
    -- This makes OSRM strongly avoid these but still allows fallback routing
    speed = 1  -- ~0.6 MPH — effectively blocked unless no alternative
  elseif highway == 'service' then
    -- Service roads: 10 MPH penalty (last-mile connectors only)
    speed = profile.service_speed_kmh
  end

  -- Apply unpaved penalty
  if surface_type == 'unpaved' and is_cart_legal then
    speed = speed * profile.penalty_unpaved
  end

  -- Set results
  result.forward_mode = mode.driving
  result.backward_mode = mode.driving
  result.forward_speed = speed
  result.backward_speed = speed

  -- Handle oneway
  local oneway = way:get_value_by_key('oneway')
  if oneway == 'yes' or oneway == '1' or oneway == 'true' then
    result.backward_mode = mode.inaccessible
  elseif oneway == '-1' then
    result.forward_mode = mode.inaccessible
  end

  -- Set road name for navigation instructions
  local name = way:get_value_by_key('name')
  local ref = way:get_value_by_key('ref')
  if name then
    result.name = name
  end
  if ref then
    result.ref = ref
  end
end

function process_turn(profile, turn)
  if turn.is_u_turn then
    turn.duration = turn.duration + profile.properties.u_turn_penalty
  end

  if turn.has_traffic_light then
    -- At signalized intersections, apply a small standard delay
    -- but this is much preferred over unsignalized crossings
    turn.duration = turn.duration + profile.properties.traffic_signal_penalty
  end
end

return {
  setup = setup,
  process_way = process_way,
  process_node = process_node,
  process_turn = process_turn,
}
