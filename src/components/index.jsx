import { motion,useMotionValue,useSpring } from 'framer-motion'
import { useEffect,useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
export function Card({children,className='',...props}) { return <motion.section initial={{opacity:0,y:5}} animate={{opacity:1,y:0}} whileHover={{y:-2,boxShadow:'0 16px 34px rgba(0,0,0,.22)',borderColor:'rgba(130,152,255,.34)'}} transition={{duration:.2,ease:'easeOut'}} className={'card '+className} {...props}>{children}</motion.section> }
export function Heading({title,sub,action}) { return <div className="heading"><div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{action}</div> }
export function Title({eyebrow,title,description,action}) { return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div> }
export function Pill({children,tone='neutral',dot=false}) { return <span className={'pill '+tone}>{dot&&<i aria-hidden="true"/>}<span>{children}</span></span> }
export function Button({children,icon:Icon,variant='',...props}) { return <button className={'button '+variant} {...props}>{Icon&&<Icon size={14} />}{children}</button> }
export function Progress({value,tone=''}) { return <div className="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={value}><motion.div className={'fill '+tone} style={{transformOrigin:'left center'}} initial={{scaleX:0}} animate={{scaleX:value/100}} transition={{duration:.9,ease:[.22,1,.36,1]}}/></div> }
export function AnimatedValue({value,className='',suffix=''}) { const motionValue=useMotionValue(0);const spring=useSpring(motionValue,{stiffness:90,damping:20,mass:.8});const [display,setDisplay]=useState(0);useEffect(()=>{const unsubscribe=spring.on('change',latest=>setDisplay(Math.round(latest)));motionValue.set(Number(value)||0);return unsubscribe},[motionValue,spring,value]);return <motion.span className={className}>{display.toLocaleString()}{suffix}</motion.span> }
export function Ring({ score = 84, size = 150 }) {
	const radius = (size - 10) / 2
	const circumference = 2 * Math.PI * radius

	return (
		<div className="ring" style={{ width: size, height: size }}>
			<svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
				<circle
					className="ring-bg"
					cx={size / 2}
					cy={size / 2}
					r={radius}
					strokeWidth="10"
				/>
				<motion.circle
					className="ring-fg"
					cx={size / 2}
					cy={size / 2}
					r={radius}
					strokeWidth="10"
					strokeDasharray={circumference}
					initial={{ strokeDashoffset: circumference }}
					animate={{ strokeDashoffset: circumference * (1 - score / 100) }}
					transition={{ duration: 1.2 }}
					transform={`rotate(-90 ${size / 2} ${size / 2})`}
				/>
			</svg>
			<div className="ring-label">
				<b><AnimatedValue value={score}/></b>
				<span>out of 100</span>
			</div>
		</div>
	)
}
export function LinkAction({to='#',children}) { return <Link className="link" to={to}>{children}<ArrowRight size={16}/></Link> }
