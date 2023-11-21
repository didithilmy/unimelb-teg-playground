using UnityEngine;
using System.Collections.Generic;
using System;
using System.Threading;
using ITS.Utils;
using UnityEngine.Serialization;
using Random = UnityEngine.Random;

namespace ITS.AI
{
// ReSharper disable once CheckNamespace
// ReSharper disable once InconsistentNaming
    public partial class TSTrafficAI : MonoBehaviour
    {
        #region public and serialized members
        [Header("Debug settings")] public Color myColor;
        [Header("General Settings")]
        [FormerlySerializedAs("LOOKAHEAD_FACTOR")]
        public float lookAheadFactor = 0.33f;
        public Transform[] frontWheels;
        [FormerlySerializedAs("LOOKAHEAD_CONST")]
        public float lookAheadConstant = 3.0f;
        public TSLaneInfo.VehicleType myVehicleType = TSLaneInfo.VehicleType.Light;
        public float reservePointDistanceMultiplier = 2.5f;
        public float minConnectorRequestDistance = 50f;
        public float lengthMarginMin = 1.5f;
        public float lengthMarginMax = 3f;
        public float lengthMarginJunctions = 5f;
        public float minDistanceToOvertake = 15f;
        public float minBrakingDistRoadblock = 10f;
        [Tooltip("This is a multiplier of the Lane max speed used to calculate the random max speed of the vehicle Random.Range(Lane Max speed * minSpeedPercent, Lane Max Speed)")]
        public float minSpeedPercent = 0.5f;
        [SerializeField] private Transform _myTransform;
        [HideInInspector] public bool reservedForEventTrigger = false;
        [HideInInspector] public bool ignoreTrafficLight = false;
        [HideInInspector] public bool crashed = false;
        #endregion
        
        #region AI Modules
        private string[] aiModulesNames = new[]
        {
            "ITS.AI.TSTrafficAI+TSPointReservationModule",
            "ITS.AI.TSTrafficAI+TSBrakeModule", "ITS.AI.TSTrafficAI+TSNavigationModule",
            "ITS.AI.TSTrafficAI+TSRespawnModule", "ITS.AI.TSTrafficAI+TSLaneSwitchModule",
            "ITS.AI.TSTrafficAI+TSThrottleModule", "ITS.AI.TSTrafficAI+TSSteeringModule",
            "ITS.AI.TSTrafficAI+TSPlayerSensorModule"
        };

        private TSAIBaseModule[] _aiModules;

        public T GetModule<T>() where T : TSAIBaseModule
        {
            foreach (var t in _aiModules)
            {
                if (t is T module)
                {
                    return module;
                }
            }

            return null;
        }

        #endregion

        #region Private variables
        private bool _initialized = false;
        private bool _otherCarPresentInJunction = false;
        private float _maxSpeed = float.MaxValue;
        private float _c = 0.0f;
        private float _brake;
        private float _throttle;
        private float _halfCarDepth = 0;
        private float[] _kFriction;
        private Vector3 _carSpeed = Vector3.zero;
        private TSPathNavigation _reservationPathNavigation;
        private TSPathNavigation _brakingPathNavigation;
        private SynchronizationContext _mainThread;
        #endregion

        #region Delegates
        private Events.Events _events = new Events.Events();
        //TODO: Remove this as it should not be used this way
        private void DispatchEvent(string eventName)
        {
            _events.Dispatch(eventName);
        }
        public delegate void OnUpdateAIDelegate(float steering, float brake, float throttle, bool isUpSideDown);

        public Func<Vector3> UpdateCarSpeed;
        public Action<bool> OnTurnRight;
        public Action<bool> OnTurnLeft;
        public Action OnCloserRange;
        public Action OnFarRange;
        public OnUpdateAIDelegate OnUpdateAI;

        #endregion

        #region Properties
        public bool Initialized => _initialized;
        public bool OverTaking { get; private set; } = false;
        public float CarSpeed => _carSpeed.z;
        public float MAXLookAheadDistance { get; private set; }
        public float MAXLookAheadDistanceFullStop { get; private set; }
        public Rigidbody[] Bodies { get; private set; }
        public float CarDepth { get; private set; }
        public float CarWidth { get; private set; }
        public float CarHeight { get; private set; }
        public float CurrentSpeedSqr { get; private set; }
        public bool EarlyBrakePoint { get; private set; }
        public Transform RearPoint { get; private set; }
        public Transform FrontPoint { get; private set; }
        public bool IsUpSideDown
        {
            set => _isUpSideDown = value;
            get => _isUpSideDown;
        }
        private int ReservedPointsCount => ReservedPoints.Count;
        private Queue<TSReservedPoints> ReservedPoints { get; set; } = new Queue<TSReservedPoints>(100);
        private Transform WheelsCenter { get; set; }
        private float ChangeLaneTime { get; set; } = 0f;
        private float LengthMargin { get; set; }
        private bool FullStop { get; set; } = false;
        #endregion

        public void Awake()
        {
            _mainThread = SynchronizationContext.Current;
            Initialize();
            CreateAIModules();
            _reservationPathNavigation = new TSPathNavigation(_steeringPathNavigation);
            _brakingPathNavigation = new TSPathNavigation(_steeringPathNavigation);
        }

        private void CreateAIModules()
        {
            _aiModules = new TSAIBaseModule[aiModulesNames.Length];

            for (var index = 0; index < aiModulesNames.Length; index++)
            {
                var moduleName = aiModulesNames[index];

                _aiModules[index] =
                    (TSAIBaseModule) Activator.CreateInstance(this.GetType().Assembly.GetType(moduleName));
                _aiModules[index].Initialize(this);
            }

            foreach (var module in _aiModules)
            {
                module.PostInitialize();
            }
        }

        private void Initialize()
        {
            if (_initialized) return;
            _initialized = true;
            SetDebugColor();
            GetCachedReferences();
            CreateWheelsCenter();
            SetRandomAIValues();
            SetCarSizeAndReferencePoints();
            SetFrictionValues();
            _myTransform.name += "-(" + MyID.ToString() + ")";
        }

        private void SetFrictionValues()
        {
            _kFriction = new float[2];
            _kFriction[0] = 1f;
            _kFriction[1] = 0.4f;
            _c = _kFriction[1] * -Physics.gravity.y;
        }

        private void SetRandomAIValues()
        {
            LengthMargin = Random.Range(lengthMarginMin, lengthMarginMax);
        }

        private void SetDebugColor()
        {
            myColor = Random.ColorHSV(0f, 1f, 0f, 1f, 0f, 1f, 1f, 1f);
        }

        private void GetCachedReferences()
        {
            if (_myTransform == null)
            {
                _myTransform = transform;
            }
            
            Bodies = GetComponentsInChildren<Rigidbody>();
        }

        private void SetCarSizeAndReferencePoints()
        {
            var carSize = _myTransform.GetBoundsFromColliders();
            CarWidth = carSize.size.x;
            CarDepth = carSize.size.z;
            CarHeight = carSize.size.y;
            FrontPoint = new GameObject("frontPoint").transform;
            FrontPoint.parent = (_myTransform);
            RearPoint = new GameObject("rearPoint").transform;
            RearPoint.parent = (_myTransform);
            FrontPoint.localPosition = carSize.center + new Vector3(0, 0, carSize.extents.z);
            FrontPoint.localRotation = Quaternion.identity;
            RearPoint.localPosition = carSize.center - new Vector3(0, 0, carSize.extents.z);
            RearPoint.localRotation = Quaternion.identity;
            _halfCarDepth = CarDepth * 0.5f;
        }

        private void Start()
        {
            if (_lanes == null)
            {
                _lanes = FindObjectOfType<TSMainManager>().lanes;
            }

            InitializeCarOccupationLength();
        }

        private void InitializeCarOccupationLength()
        {
            CarOccupationLenght = CarDepth + LengthMargin * 2f;
        }

        public void InitializeMe()
        {
            Initialize();
        }

        private Vector3 _forward;
        private Vector3 _position;
        private Quaternion _rotation = Quaternion.identity;
        private Vector3 _localEulerAngles;
        private Vector3 _frontPointPosition;
        private Quaternion _frontPointRotation = Quaternion.identity;
        private Vector3 _rearPointPosition;
        private Quaternion _rearPointRotation = Quaternion.identity;
        private Vector3 _wheelsCenterPosition;
        private Quaternion _wheelsCenterRotation = Quaternion.identity;
        private float _time;

        private void FixedUpdate()
        {
            UpdateAllCachedFields();
            if (UpdateCarSpeed != null)
            {
                _carSpeed = UpdateCarSpeed();
            }

            if (_multiThreading == false)
            {
                FixedUpdateMe();
            }

            UpdateOutputs();
            UpdateAIModulesMainThread();
        }

        private void UpdateAllCachedFields()
        {
            _time = Time.time;
            _deltaTime = Time.deltaTime;
            _wheelsCenterPosition = WheelsCenter.position;
            _wheelsCenterRotation = WheelsCenter.rotation;
            _forward = _myTransform.forward;
            _position = _myTransform.position;
            _rotation = _myTransform.rotation;
            _localEulerAngles = _myTransform.localEulerAngles;
            _frontPointPosition = FrontPoint.position;
            _frontPointRotation = FrontPoint.rotation;
            _rearPointPosition = RearPoint.position;
            _rearPointRotation = RearPoint.rotation;
        }

        private Vector3 InverseTransformPoint(Vector3 transforPos, Quaternion transformRotation, Vector3 transformScale,
            Vector3 pos)
        {
            Matrix4x4 matrix = Matrix4x4.TRS(transforPos, transformRotation.normalized, transformScale);
            Matrix4x4 inverse = matrix.inverse;
            return inverse.MultiplyPoint3x4(pos);
        }

        public void FixedUpdateMe()
        {
            UpdateLookahead();
            UpdateCurrentSpeedSqr();
            UpdateNextCarSpeedIfTrafficLightPresent();
            UpdateMaxLookAheadDistance();
            ControllerAI();
        }

        private void ControllerAI()
        {
            UpdateAIModules();
        }

        private void UpdateOutputs()
        {
            _throttle = Mathf.Clamp01(_throttle - _externalBrake);
            _brake = Mathf.Clamp01(_brake + _externalBrake);
            _steering = Mathf.Clamp(_steering, -1f, 1f);
            OnUpdateAI?.Invoke(_steering, _brake, _throttle, _isUpSideDown);
        }

        private float GetCurrentLaneMaxSpeed()
        {
            System.Random random = new System.Random();
            var currentMaxSpeed = Mathf.Lerp(_steeringPathNavigation.CurrentLane.maxSpeed * minSpeedPercent,
                _steeringPathNavigation.CurrentLane.maxSpeed, Convert.ToSingle(random.NextDouble())).KphToMPS();
            return currentMaxSpeed;
        }


        private void UpdateAIModules()
        {
            foreach (var module in _aiModules)
            {
                module.OnFixedUpdate();
            }
        }

        private void UpdateAIModulesMainThread()
        {
            foreach (var module in _aiModules)
            {
                module.OnFixedUpdateMainThread();
            }
        }

        private void UpdateMaxLookAheadDistance()
        {
            var aerodynamicsFactor = (2.0f * _c);
            var factorInverted = 1f / aerodynamicsFactor;
            MAXLookAheadDistance = (CurrentSpeedSqr - _nextCarSpeedSqr) * factorInverted;
            MAXLookAheadDistanceFullStop = CurrentSpeedSqr * factorInverted;

            if (MAXLookAheadDistance < 0)
            {
                MAXLookAheadDistance = 0;
            }

            if (MAXLookAheadDistanceFullStop < 0)
            {
                MAXLookAheadDistanceFullStop = 0;
            }

            MAXLookAheadDistance += LengthMargin;
            MAXLookAheadDistanceFullStop += LengthMargin;
            _sqrMaxLookAheadDistance = MAXLookAheadDistanceFullStop * MAXLookAheadDistanceFullStop;
        }

        private void UpdateNextCarSpeedIfTrafficLightPresent()
        {
            if (!(_reservationPathNavigation.CurrentLane is TSLaneConnector nextConnectorInstance))
            {
                return;
            }

            var hasNoRemainingTime = nextConnectorInstance.remainingGreenLightTime < 0f;
            if (hasNoRemainingTime)
            {
                return;
            }

            var distanceToRun = CarSpeed * nextConnectorInstance.remainingGreenLightTime;
            var distance = nextConnectorInstance.points[0].point + PointOffset - FrontPoint.position;
            var nextConnectorDistance = distance.magnitude + nextConnectorInstance.totalDistance;

            if (distanceToRun < nextConnectorDistance)
            {
                _nextCarSpeedSqr = 0;
            }
        }

        private float _nextCarSpeedSqr = 0;
        private float _sqrMaxLookAheadDistance = 0;
        private float _steering;
        private bool _overtake;
        private float _deltaTime;
        private bool _multiThreading;
        private float _externalBrake;
        private readonly object _reservedPointsLockObject = new object();

        private float GetCurrentPointDistance()
        {
            var localPointPos = InverseTransformPoint(_frontPointPosition, _frontPointRotation, Vector3.one,
                _reservationPathNavigation.CurrentWaypoint.point +
                PointOffset); // FrontPoint.InverseTransformPoint(_reservationPathNavigation.CurrentWaypoint.point + PointOffset);
            var currentPointDistance = localPointPos.magnitude * Mathf.Sign(localPointPos.z);
            //var currentPointDistance = Vector3.Distance(_frontPointPosition, _reservationPathNavigation.CurrentWaypoint.point + PointOffset);
            if (Mathf.Abs(localPointPos.x) > CarDepth) currentPointDistance = Mathf.Abs(currentPointDistance);

            if (_otherCarPresentInJunction)
            {
                currentPointDistance -= lengthMarginJunctions;
            }

            return currentPointDistance;
        }

        private void UpdateLookahead()
        {
            var lookAheadFactorBySpeed = lookAheadFactor * Mathf.Clamp(CarSpeed * 0.006666667f, 0.1f, 1f);
            LookAheadDistance = lookAheadConstant + CarSpeed * lookAheadFactorBySpeed;
        }

        private void UpdateCurrentSpeedSqr()
        {
            CurrentSpeedSqr = CarSpeed * CarSpeed;
        }

        private void CreateWheelsCenter()
        {
            var bounds = TSUtils.GetBoundsFromTransforms(frontWheels);
            WheelsCenter = new GameObject().transform;
            var wheelsCenterTransform = WheelsCenter.transform;
            wheelsCenterTransform.rotation = Quaternion.identity;
            wheelsCenterTransform.position = new Vector3(bounds.center.x, 0f, bounds.center.z);
            wheelsCenterTransform.parent = _myTransform;
            WheelsCenter.name = "FrontWheelsCenter";
        }

        public bool IsEnabled { get; private set; } = false;
        public bool Spawning { get; set; } = false;
        public Transform Transform => _myTransform;

        public void Enable()
        {
            crashed = false;
            foreach (var t in Bodies)
            {
                t.constraints = RigidbodyConstraints.None;
                t.velocity = Vector3.zero;
                t.angularVelocity = Vector3.zero;
            }
            gameObject.SetActive(true);
            
            if (_multiThreading)
            {
                UpdateAllCachedFields();
            }
            
            IsEnabled = true;
        }

        public void Disable(bool disableGameObject = true, bool immediate = false)
        {
            IsEnabled = false;
            _throttle = 0f;
            _brake = 0f;
            _externalBrake = 0f;

            if (_multiThreading && immediate == false)
            {
                _mainThread.Send((d) => { InternalDisable(disableGameObject); }
                    , this);
            }
            else
            {
                InternalDisable(disableGameObject);
            }
        }

        public void UnPause()
        {
            IsEnabled = true;
        }
        
        public void Pause()
        {
            IsEnabled = false;
            _throttle = 0;
            _brake = 1f;
            UpdateOutputs();
        }

        private void InternalDisable(bool disableGameObject)
        {
            OnUpdateAI?.Invoke(0, 0, 0, _isUpSideDown);
            foreach (var t in Bodies)
            {
                t.constraints = RigidbodyConstraints.FreezeAll;
            }

            TurnOffTurningLights();
            
            UnReserveAll();
            gameObject.SetActive(!disableGameObject);

            // Additional line for Traffic AI
            Destroy(gameObject);
        }

        private void SetLane(TSLaneInfo lane)
        {
            _reservationPathNavigation.CurrentLane = lane;
            _brakingPathNavigation.CurrentLane = lane;
        }

        private void AddBrake(float brakeValue)
        {
            _brake += brakeValue;
            _brake = Mathf.Clamp01(_brake);
        }

        private void SetThrottle(float throttleValue)
        {
            _throttle = throttleValue;
        }

        public void InitializeWaypointsData(TSLaneInfo newCurrentLane, int newPreviousWaypointCurve,
            int newCurrentWaypoint, int newPreviousWaypoint, bool? respawnIfUpsideDown = null)
        {
            RespawnIfUpsideDown = respawnIfUpsideDown ?? RespawnIfUpsideDown;
            _previousSteerWaypointIndex = newPreviousWaypoint;
            _lastReservedPoint = null;
            SegDistance = 0;
            _reservationPathNavigation.Clear();
            _brakingPathNavigation.Clear();
            _steeringPathNavigation.Clear();
            _steeringPathNavigation.SetCurrentPointIndex(newCurrentWaypoint);
            _reservationPathNavigation.SetCurrentPointIndex(newPreviousWaypointCurve);
            _brakingPathNavigation.SetCurrentPointIndex(newPreviousWaypointCurve);
            SetCurrentLane(newCurrentLane);
            SetLane(newCurrentLane);
            AddNextTrackToPath();
            AddCurrentLaneTotalOccupation(Mathf.Round(CarOccupationLenght / newCurrentLane.totalDistance * 100f));
            AddOccupiedLane(newCurrentLane);
        }

        private void ReduceSegDistance(float pointDistanceToNextPoint)
        {
            SegDistance -= pointDistanceToNextPoint;
        }

        private void UpdateCurrentMaxSpeed()
        {
            _maxSpeed = GetCurrentLaneMaxSpeed();
        }

        private void AddOccupiedLane(TSLaneInfo lane)
        {
            lock (_occupiedLanesLock)
            {
                if (OccupiedLanes.Contains(lane))
                {
                    return;
                }

                OccupiedLanes.Enqueue(lane);
            }
        }

        private void TurnOffTurningLights()
        {
            _isTurning = false;
            OnTurnLeft?.Invoke(false);
            OnTurnRight?.Invoke(false);
        }

        private void UnReserveAll()
        {
            shouldDisable = false;
            UnReserveAllReservedConnectors();
            ResetAllOccupiedLanes();
            UnReserveAllReservedPoints();
            DispatchEvent(Events.Events.EventNames.UnReserveAll);
            SegDistance = 0f;
        }

        private void UnReserveAllReservedPoints()
        {
            while (ReservedPoints.Count > 0)
            {
                TSReservedPoints tsReservedPoints;
                lock (_reservedPointsLockObject)
                {
                    tsReservedPoints = ReservedPoints.Dequeue();
                }

                tsReservedPoints.Point.TryUnReservePoint(MyID);

                if (tsReservedPoints.isConnector)
                {
                    UnReserveNearConnectorPoints(tsReservedPoints.Point as TSConnectorPoint);
                }
            }
        }

        private void ResetAllOccupiedLanes()
        {
            lock(_occupiedLanesLock)
            {
                while (OccupiedLanes.Count > 0)
                {
                    var tsLaneInfo = OccupiedLanes.Dequeue();
                    tsLaneInfo.DecreaseTotalOccupation(Mathf.Round(CarOccupationLenght / tsLaneInfo.totalDistance * 100f));
                }

                OccupiedLanes.Clear();
            }
        }

        private void UnReserveAllReservedConnectors()
        {
            while (_reservedConnectors.Count > 0)
            {
                UnReserveLaneIdOnNextReservedConnector();
            }
        }

        public void ResetRoute()
        {
            _steeringPathNavigation.Clear();
            TurnOffTurningLights();
            AddNextTrackToPath();
        }

        private void AddNextTrackToPath()
        {
            var max = Mathf.Max(MAXLookAheadDistanceFullStop, LookAheadDistance);
            var distance = max * reservePointDistanceMultiplier + CarDepth;
            if (shouldDisable)
            {
                return;
            }

            shouldDisable = _steeringPathNavigation.TryAddPath(distance, myVehicleType) == false && _steeringPathNavigation.NoMorePath;
        }


        public void AddNextTrackToPath(List<TSNextLaneSelection> newPath, int point)
        {
            _previousSteerWaypointIndex = point;
            _lastReservedPoint = null;
            SegDistance = 0;
            _reservationPathNavigation.Clear();
            _brakingPathNavigation.Clear();
            _steeringPathNavigation.Clear();
            _steeringPathNavigation.SetCurrentPointIndex(point);
            _reservationPathNavigation.SetCurrentPointIndex(point);
            _brakingPathNavigation.SetCurrentPointIndex(point);
            var newCurrentLane = newPath[0].NextLane;
            SetCurrentLane(newCurrentLane);
            SetLane(newCurrentLane);
            AddCurrentLaneTotalOccupation(Mathf.Round(CarOccupationLenght / newCurrentLane.totalDistance * 100f));
            AddOccupiedLane(newCurrentLane);
            _steeringPathNavigation.AddPath(newPath);
        }

        private void UnReserveNearConnectorPoints(TSConnectorPoint points)
        {
            points?.UnReserveOtherConnectorPoints(MyID);
        }

        private void UnReserveLaneIdOnNextReservedConnector()
        {
            if (_reservedConnectors.Count == 0)
            {
                return;
            }

            var connector = _reservedConnectors.Dequeue();
            connector.UnReserveLaneIdOnNearConnectorPoints(MyID, CarOccupationLenght);
        }

        private void AddCurrentLaneTotalOccupation(float occupation)
        {
            ((TSLaneInfo) _steeringPathNavigation.CurrentLane).AddOccupation(occupation);
        }

        private void SetLastLaneIndex(TSLaneInfo managerLane)
        {
            LastLaneIndex = managerLane;
        }

        private void SetCurrentLane(TSLaneInfo managerLane)
        {
            _steeringPathNavigation.CurrentLane = managerLane;
            SetLastLaneIndex(managerLane);
            UpdateCurrentMaxSpeed();
            _relativeWaypointPosition = Vector3.zero;
            _relativeWaypointPositionOnCar = Vector3.zero;
            RelativeWPosMagnitude = 0;
        }

        public void ReservedPointsEnqueue(Queue<TSReservedPoints> tsReservedPoints)
        {
            lock (_reservedPointsLockObject)
            {
                foreach (var point in tsReservedPoints)
                {
                    ReservedPoints.Enqueue(point);
                }
            }
        }

        public void Setlanes(TSLaneInfo[] managerLanes)
        {
            _lanes = managerLanes;
        }

        #region Gizmos

        private void OnDrawGizmosSelected()
        {
            if (!Application.isPlaying) return;
            DrawReservedPoints();
            DrawCurrentPoint();
            //DrawChangeLaneReservedPoints();
            DrawReservedConnectors();
            DrawCurrentPath();
            DrawCurrentWaypoint();
            foreach (var module in _aiModules)
            {
                module.OnDrawGizmosSelected();
            }
        }

        private void DrawCurrentPoint()
        {
            Gizmos.color = _reservationPathNavigation.CurrentWaypoint.ReservationID == 0 ? Color.green : Color.red;
            Gizmos.DrawCube(_reservationPathNavigation.CurrentWaypoint.point, Vector3.one * CarWidth);
        }

        private void DrawReservedPoints()
        {
            Gizmos.color = Color.green;
            bool first = true;
            lock (_reservedPointsLockObject)
            {
                foreach (var resP in ReservedPoints)
                {
                    Gizmos.color = first? Color.magenta : resP.Point.CarWhoReserved == null && resP.Point.ReservationID == 0 ? Color.blue :
                        resP.Point.CarWhoReserved != this ? Color.red : Color.green;
                    Gizmos.DrawWireSphere(resP.Point.point + PointOffset, CarWidth);
                    first = false;
                }
            }
        }

        private void DrawReservedConnectors()
        {
            Gizmos.color = Color.red;
            foreach (TSLaneConnector connector in _reservedConnectors)
            {
                Gizmos.DrawLine(connector.conectorA + PointOffset, connector.conectorB + PointOffset);
            }
        }

        private void DrawCurrentPath()
        {
            for (var index = 0; index < _steeringPathNavigation.Count; index++)
            {
                TSNextLaneSelection nextLane = _steeringPathNavigation[index];
                if (nextLane.IsNull){continue;}
                if (nextLane.IsConnector)
                {
                    Gizmos.color = Color.cyan;
                    Gizmos.DrawLine(nextLane.NextConnector.conectorA + PointOffset,
                        nextLane.NextConnector.conectorB + PointOffset);
                }
                else
                {
                    Gizmos.color = Color.magenta;
                    Gizmos.DrawLine(nextLane.NextLane.conectorA + PointOffset,
                        nextLane.NextLane.conectorB + PointOffset);
                }
            }
        }

        private void DrawCurrentWaypoint()
        {
            Gizmos.color = Color.magenta;
            Gizmos.DrawSphere(_steeringPathNavigation.CurrentWaypoint.point + PointOffset, CarWidth);
        }

        #endregion

        public void SetIsMultithreading(bool multiThreading)
        {
            _multiThreading = multiThreading;
        }

        private void AddExternalBrake(float brake)
        {
            _externalBrake = brake;
        }
    }
}